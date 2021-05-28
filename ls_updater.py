#!/usr/bin/env python3

import datetime
import json
import logging.handlers
import os
import shutil
import subprocess
import sys
from pathlib import Path

import requests
import wget
from bs4 import BeautifulSoup

"""
    ls_updater: LimeSurvey update assistant 
    By Noah Kruiper
"""

#################
# Initial Setup #
#################

config = {}

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s {%(filename)s:%(lineno)d} [%(levelname)s]: %(message)s")


#############
# Utilities #
#############

def __log_setup(stdout, syslog, file):
    """Logging config
    :param stdout: Output to console
    :param syslog: Output to local syslog
    :param file: Output to a rotating file
    """
    global log, formatter
    if stdout:
        stdout_handler = logging.StreamHandler(sys.stdout)
        stdout_handler.setFormatter(formatter)
        stdout_handler.setLevel(logging.INFO)
        log.addHandler(stdout_handler)
    if syslog:
        syslog_handler = logging.handlers.SysLogHandler(address="/dev/log")
        syslog_handler.setFormatter(formatter)
        syslog_handler.setLevel(logging.INFO)
        log.addHandler(syslog_handler)
    if file:
        if not os.path.exists("logs"):
            os.makedirs("logs")
        file_handler = logging.handlers.RotatingFileHandler('logs/ls_updater.log', maxBytes=50000, backupCount=10)
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.INFO)
        log.addHandler(file_handler)
    if stdout or syslog or file:
        log.debug("Set up logger. Stdout: " + str(stdout) + ", Syslog: " + str(syslog) + ", File: " + str(file))
        log.info("================================")
        log.info("New run started at: " + str(datetime.datetime.now()))
        log.info("================================")


def validate_config(config_input):
    if config_input is None or len(config_input) < 1:
        raise RuntimeError("Config may exist, but is apparently empty.")
    expected_options = ["branch", "db_cnf_path", "db_name", "db_port", "db_server", "install_octal_permissions",
                        "install_owner", "install_path", "log_to_file", "log_to_stdout", "log_to_syslog",
                        "web_server_init_system", "web_server_service"]
    for option in expected_options:
        if config[option] is None or config[option] == "":
            raise RuntimeError("Config validation error: empty " + option)
    if config['branch'] not in ["lts", "unstable", "dev"]:
        raise RuntimeError("Config validation error: branch not one of 'lts', 'unstable', 'dev': "
                           + str(config['branch']))
    elif not os.path.exists(config['install_path']):
        raise RuntimeError("Config validation error: install_path does not exist.")
    # elif not os.access(config['db_cnf_path'], os.R_OK):
    #     raise RuntimeError(
    #         "Config validation error: db_cnf_path does not allow read permission: " + str(config['db_cnf_path']))
    elif not os.access(config['install_path'], os.W_OK | os.X_OK):
        raise RuntimeError(
            "Config validation error: install_path does not allow write and execute permissions: "
            + str(config['install_path']))
    elif not config["web_server_init_system"] in ['generic', 'service', 'systemd', 'systemctl', 'init.d', 'openrc',
                                                  'rc.d', 'upstart', 'finit', 'initctl', 'epoch']:
        raise RuntimeError("Config validation error: web_server_init_system not one of "
                           "'generic' (or 'service'), systemd, 'init.d' (or 'openrc'), 'rc.d', "
                           "'upstart' (or 'finit'), or 'epoch': " + str(config['branch']))
    return True


#######################
# Run the main script #
#######################

def run():
    global config, log
    # load the configuration
    try:
        with open(os.path.normpath(Path(__file__).parent.absolute()) + "/" + "config.json", "r") as file:
            config = json.load(file)
        validate_config(config)
        __log_setup(config["log_to_stdout"], config["log_to_syslog"], config['log_to_file'])
        log.info("Loaded configuration from disk.")
    except Exception as e:
        print("Unable to load and validate configuration. Now exiting. Full error: " + str(e), file=sys.stderr)
        exit(1)
    # check currently installed version from limesurvey/application/config/version.php
    version_code = ""
    try:
        with open(config["install_path"] + "/application/config/version.php", "r") as f:
            current_version = f.read().split("$config['versionnumber'] = '")[1].split("';\n$config")[0]
            f.close()
        with open(config["install_path"] + "/application/config/version.php", "r") as f:
            current_build = f.read().split("$config['buildnumber'] = ")[1].split(";\n$config")[0].strip("'")
            f.close()
        version_code = current_version + "+" + current_build
        log.info("Current LimeSurvey version: " + version_code)
    except Exception as e:
        log.error("Unable to determine current LimeSurvey version. Now exiting. Full error: " + str(e))
        exit(1)

    log.info("Retrieving latest releases from https://community.limesurvey.org/downloads/")
    page = None
    try:
        page = requests.get("https://community.limesurvey.org/downloads/")
    except Exception as e:
        log.error("Unable to retrieve releases page. Now exiting. Full error: " + str(e))
        exit(1)

    log.info("Parsing releases page...")
    releases = []
    try:
        soup = BeautifulSoup(page.content, "html.parser")
        rows = soup.find_all("a", {"class": ["release-button"]})
        for num, row in enumerate(rows):
            url = row.attrs["href"]
            if "lts" in url:
                release_type = "lts"
            elif "latest-stable" in url:
                release_type = "unstable"
            elif "unstable-releases" in url:
                release_type = "dev"
            else:
                log.error("Unable to locate release within the page HTML. Now exiting. Full error: " + str(e))
                exit(1)
            version = url.split("/").pop().split("limesurvey").pop().split("+")[0]
            build = url.split("/").pop().split("limesurvey").pop().split("+").pop().split(".zip")[0]
            release_code = version + "+" + build
            releases.append({"release_code": release_code,
                             "type": release_type,
                             "url": url})
            url.split("/").pop()
        log.info("Available versions: " + str(releases).replace("\n", "\t"))
    except Exception as e:
        log.error("Unable to parse HTML of webpage for releases. Now exiting. Full error: " + str(e))
        exit(1)

    # Select version to install
    new_version = None
    url = None
    for release in releases:
        if release["type"] == config["branch"]:
            new_version = release["release_code"]
            url = release["url"]
            break
    if new_version is None:
        log.error("Unable to find compatible version. Check the logs and verify the branch set in config.json.")
        exit(1)
    if new_version == current_version:
        log.info("No need to upgrade. Current version is the most recent for the '" + config["branch"] + "' branch.")
        exit(0)
    log.info("Version to install: " + new_version)
    filename = new_version + ".zip"
    log.info("Downloading release: " + url)
    filename_on_disk = ""
    try:
        if not os.path.exists("ls_downloads"):
            os.makedirs("ls_downloads")
        if os.path.exists("ls_downloads/" + filename):
            log.info("Removing existing file: ls_downloads/" + filename)
            os.remove("ls_downloads/" + filename)
        filename_on_disk = wget.download(url, "ls_downloads/" + filename)
    except Exception as e:
        log.error("Unable to download. Now exiting. Full error: " + str(e))
        exit(1)
    log.info("Downloaded release: " + filename_on_disk)

    log.info("Extracting release from zip: " + filename_on_disk)
    try:
        if os.path.exists("ls_downloads/" + new_version):
            log.info("Removing existing folder: ls_downloads/" + new_version)
            shutil.rmtree("ls_downloads/" + new_version)
        shutil.unpack_archive(filename_on_disk, "ls_downloads/" + new_version)
    except Exception as e:
        log.error("Unable to unzip release. Now exiting. Full error: " + str(e))
        exit(1)

    log.info("Stopping web server service: " + config["web_server_service"]
             + " with init system: " + config["web_server_init_system"])
    try:
        if config["web_server_init_system"] in ["systemd", "systemctl"]:
            subprocess.run(["systemctl", "stop", config["web_server_service"]], capture_output=True, check=True)
        elif config["web_server_init_system"] in ["service", "generic"]:
            subprocess.run(["service", config["web_server_service"], "stop"], capture_output=True, check=True)
        elif config["web_server_init_system"] in ["init.d", "openrc"]:
            subprocess.run(["/etc/init.d/" + config["web_server_service"], "stop"], capture_output=True, check=True)
        elif config["web_server_init_system"] == "rc.d":
            subprocess.run(["/etc/rc.d/" + config["web_server_service"], "stop"], capture_output=True, check=True)
        elif config["web_server_init_system"] in ["upstart", "finit", "initctl"]:
            subprocess.run(["initctl", "stop", config["web_server_service"]], capture_output=True, check=True)
        elif config["web_server_init_system"] == "epoch":
            subprocess.run(["epoch", "stop", config["web_server_service"]], capture_output=True, check=True)
        log.info("Stopped web server.")
    except subprocess.CalledProcessError as e:
        if e.output is not None and e.output != b"":
            log.error("Unable to stop web server cleanly. Now exiting. Full error: " + str(e)
                      + " and command output: " + str(e.output))
        else:
            log.error("Unable to stop web server cleanly. Now exiting. Full error: " + str(e))
        exit(1)

    log.info("Backing up database: " + config["db_name"])
    build_change = version_code + "_to_" + new_version
    backup_path = "ls_backup/" + build_change + "/"
    if os.path.exists(backup_path + config["db_name"] + ".sql"):
        log.error(
            "DB backup already exists: " + backup_path + config["db_name"] + ".sql so now exiting.")
        exit(1)
    try:
        if not os.path.exists(backup_path):
            os.makedirs(backup_path)
    except Exception as e:
        log.error("Unable to create directory " + backup_path + " so now exiting. Full error: " + str(e))
        exit(1)
    try:
        subprocess.run(["mysqldump", "--defaults-extra-file=" + config["db_cnf_path"],
                        "-h", config["db_server"],
                        "-P", str(config["db_port"]),
                        config["db_name"],
                        "--result-file=" + backup_path + config["db_name"] + ".sql"],
                       capture_output=True,
                       check=True)
    except subprocess.CalledProcessError as e:
        if e.output is not None and e.output != b"":
            log.error("Unable to back up database. Now exiting. Full error: " + str(e)
                      + " and command output: " + str(e.output))
        else:
            log.error("Unable to back up database. Now exiting. Full error: " + str(e))
        exit(1)

    log.info("Backing up application files from " + config["install_path"] + " to " + backup_path)
    if os.path.exists(backup_path + version_code + "_backup.zip"):
        log.error("Backup already exists: " + backup_path + version_code + "_backup.zip so now exiting.")
        exit(1)
    try:
        shutil.make_archive(backup_path + version_code + "_backup", "zip",
                            config["install_path"])
    except Exception as e:
        log.error("Unable to zip and back up the current installation. Now exiting. Full error: " + str(e))
        exit(1)

    log.info("Copying needed files for restore from " + config["install_path"] + " to "
             + backup_path)
    try:
        shutil.copytree(config["install_path"] + "/upload",
                        backup_path + "upload",
                        symlinks=False,
                        ignore=None,
                        copy_function=shutil.copy2,
                        ignore_dangling_symlinks=False,
                        dirs_exist_ok=True)
        shutil.copy2(config["install_path"] + "/application/config/config.php",
                     backup_path + "config.php")
        if current_version.startswith("4") or current_version.startswith("5"):
            # the security file is only present in 4.x and 5.x
            shutil.copy2(config["install_path"] + "/application/config/security.php",
                         backup_path + "security.php")
    except Exception as e:
        log.error("Unable to copy needed files. Now exiting. Full error: " + str(e))
        exit(1)

    log.info("Deleting existing application files from " + config["install_path"])
    try:
        shutil.rmtree(config["install_path"], ignore_errors=False, onerror=None)
    except Exception as e:
        log.error("Unable to delete existing application files. Now exiting. Full error: " + str(e))
        exit(1)

    log.info("Moving new application files to " + config["install_path"])
    try:
        # delete upload directory since it"s getting replaced
        shutil.rmtree("ls_downloads/" + new_version + "/limesurvey/upload")
        shutil.move("ls_downloads/" + new_version + "/limesurvey",
                    config["install_path"],
                    copy_function=shutil.copy2)
    except Exception as e:
        log.error("Unable to move new application files. Now exiting. Full error: " + str(e))
        exit(1)

    log.info("Restoring needed files from " + backup_path + " to " + config["install_path"])
    try:
        shutil.move(backup_path + "upload",
                    config["install_path"],
                    copy_function=shutil.copy2)
        shutil.move(backup_path + "config.php",
                    config["install_path"] + "/application/config/",
                    copy_function=shutil.copy2)
        if current_version.startswith("4") or current_version.startswith("5"):
            # the security file is only present in 4.x and 5.x
            shutil.move(backup_path + "security.php",
                        config["install_path"] + "/application/config/",
                        copy_function=shutil.copy2)
    except Exception as e:
        log.error("Unable to restore existing application files. Now exiting. Full error: " + str(e))
        exit(1)

    log.info("Setting ownership of install path: " + config["install_path"] + " to owner: " + config["install_owner"])
    try:
        subprocess.run(["chown", "-R", "www-data:www-data", config["install_path"]], capture_output=True,
                       check=True)
    except subprocess.CalledProcessError as e:
        if e.output is not None and e.output != b"":
            log.error(
                "Unable to apply ownership. Now exiting. Full error: " + str(e) + " and command output: " + str(
                    e.output))
        else:
            log.error("Unable to apply ownership. Now exiting. Full error: " + str(e))
        exit(1)

    log.info("Applying octal permissions: " + config["install_octal_permissions"]
             + " to install path: " + config["install_path"])
    try:
        subprocess.run(["chmod", "-R", config["install_octal_permissions"], config["install_path"]],
                       capture_output=True, check=True)
    except subprocess.CalledProcessError as e:
        if e.output is not None and e.output != b"":
            log.error(
                "Unable to apply octal permissions. Now exiting. Full error: " + str(e)
                + " and command output: " + str(e.output))
        else:
            log.error("Unable to apply octal permissions. Now exiting. Full error: " + str(e))
        exit(1)

    log.info("Starting web server service: " + config["web_server_service"]
             + " with init system: " + config["web_server_init_system"])
    try:
        if config["web_server_init_system"] in ["systemd", "systemctl"]:
            subprocess.run(["systemctl", "start", config["web_server_service"]], capture_output=True, check=True)
        elif config["web_server_init_system"] in ["service", "generic"]:
            subprocess.run(["service", config["web_server_service"], "start"], capture_output=True, check=True)
        elif config["web_server_init_system"] in ["init.d", "openrc"]:
            subprocess.run(["/etc/init.d/" + config["web_server_service"], "start"], capture_output=True, check=True)
        elif config["web_server_init_system"] == "rc.d":
            subprocess.run(["/etc/rc.d/" + config["web_server_service"], "start"], capture_output=True, check=True)
        elif config["web_server_init_system"] in ["upstart", "finit", "initctl"]:
            subprocess.run(["initctl", "start", config["web_server_service"]], capture_output=True, check=True)
        elif config["web_server_init_system"] == "epoch":
            subprocess.run(["epoch", "start", config["web_server_service"]], capture_output=True, check=True)
        log.info("Started web server. Check your LimeSurvey install now.")
    except subprocess.CalledProcessError as e:
        if e.output is not None and e.output != b"":
            log.error(
                "Unable to start web server cleanly. Now exiting. Full error: " + str(e)
                + " and command output: " + str(e.output))
        else:
            log.error("Unable to start web server cleanly. Now exiting. Full error: " + str(e))
        exit(1)


if __name__ == "__main__":
    run()
