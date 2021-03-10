# ls_updater
Update a LimeSurvey instance using packages from the official website.

## Functionality
- Downloads application builds directly from the [LimeSurvey website](https://community.limesurvey.org/downloads/)
- Follows the [upgrade instructions](https://manual.limesurvey.org/Upgrading_from_a_previous_version#Upgrade_instructions_.28from_2.x_or_newer_to_any_later_version.29) in the LimeSurvey Manual, including differences between version 3 and 4
- Supports Stable, Unstable, and Development branches
- Performs backups of the database and application files
- Stops and starts the web server, with support for various init systems:
  - generic / `service`
  - `systemd`
  - `init.d` / `OpenRC`
  - `rc.d`
  - `Upstart` / `Finit`
  - `Epoch`

## Bird's-eye view of the script:
1. First it loads and checks the configuration in `config.json`, activating the logger accordingly
2. Then it starts the main task by loading the release page, listing available releases, and selecting the target based on the chosen branch
3. Once confirmed, it downloads the new version and stops the web server's service using the init system
4. It then dumps the database and zips up the existing install to a subfolder
5. Afterwards, it copies the new application files and restores those which need to be preserved with the correct permissions
6. Finally, the web server is started back up

## Usage:
1. **System requirements:**
    1. LimeSurvey 3+ running on GNU+Linux (tested on `Ubuntu 20.04`)
    2. Web server software managed with a one of the supported init systems (see below)
    3. Standard LimeSurvey installation without custom modifications to the core files
    4. Python 3.6+ with `bs4` (BeautifulSoup), `requests`, and `wget` packages available
    5. Root or sudo access to execute (note that the above Python packages need to be available to the root user or venv)
    6. `mysqldump` available in the `PATH`
    7. Database in MariaDB or MySQL with a `.my.cnf` file prepared with credentials (see `config.json` details below)
    8. Configured `config.json` alongside the script
2. **Running ls_updater the easy way:**
    1. Prepare system to ensure the dependencies are met (for example, by installing the required Python 3 packages with `pip`)
    2. `git pull https://github.com/xenago/ls_updater`
    3. `cd ls_updater`
    4. `nano .my.cnf` (only required if you don't already have one elsewhere - if you do, add its path to `config.json`)
    5. `cp default-config.json config.json && nano config.json` (edit to include all necessary information, details below)
    6. `sudo python3 ls_updater.py`
3. **Configuration via `config.json`:** (all included in the sample `default-config.json`, which assumes `systemd` & `nginx`)
    - `"branch"`: select the update branch. Supported values:
      - `lts` (currently, version 3)
      - `unstable` (currently, version 4)
      - `dev` (currently, version 4-DEV)
    - `"db_cnf_path"`: path to a `.my.cnf` file with database credentials
    - `"db_name"`: name of the LimeSurvey database in MySQL/MariaDB
    - `"db_port"`: port of the database server
    - `"db_server"`: hostname or IP address of the database server
    - `"install_octal_permissions"`: 755-style permissions applied to the newly-installed application files
    - `"install_owner"`: `username:group` which should own the newly-installed application files
    - `"install_path"`: path to the application files on the disk
    - `"log_to_file"`: print the output of the script to a file
    - `"log_to_stdout"`: print the output of the script to the console
    - `"log_to_syslog"`: print the output of the script to local syslog
    - `"web_server_init_system"`: select the init system used to restart the web server service. Supported values:
      - `generic`
      - `systemd`
      - `service`
      - `init.d`
      - `openrc`
      - `rc.d`
      - `upstart`
      - `finit`
      - `epoch`
    - `"web_server_service"`: systemd service name of the web server, typically `apache2` or `nginx`
