# ls_updater
Update a LimeSurvey instance using packages from the official website.

### Functionality
- Downloads application builds directly from the [LimeSurvey website](https://community.limesurvey.org/downloads/)
- Follows the [upgrade instructions](https://manual.limesurvey.org/Upgrading_from_a_previous_version#Upgrade_instructions_.28from_2.x_or_newer_to_any_later_version.29) in the LimeSurvey Manual, including differences between version 3 and 4
- Supports Stable, Unstable, and Development branches
- Performs backups of the database and application files
- Stops and starts the web server, with support for various init systems:
  - generic / "service"
  - `systemd`
  - `init.d` / `OpenRC`
  - `rc.d`
  - `Upstart` / `Finit`
  - `Epoch`

### Bird's-eye view
1. Load and verify `config.json`, configure the logger
2. Parse the release page, download the selected version
3. Stop the web server using the init system
4. Dump the database and zip up the existing install as a backup
5. Instal the new application files, restore user data files, apply permissions
6. Start the service for the web server back up

## Using ls_updater

### System requirements

  - LimeSurvey 3+ running on GNU/Linux (tested on Ubuntu 20.04)
  - Web server software managed with a one of the supported init systems, such as systemd or init.d (see below)
  - Standard LimeSurvey installation without custom modifications to the core files
  - Python 3.6+ with `bs4` (BeautifulSoup), `requests`, and `wget` packages available
  - `mysqldump` available in the `PATH`, typically installed with the `mysql-client` or `mariadb-client` packages
  - Root or sudo access to execute (note that the above Python packages and `mysqldump` need to be available)
  - Database in MariaDB or MySQL with a `.my.cnf` file prepared with credentials (see `config.json` details below)
  - Configured `config.json` alongside the script

### Using `config.json`

Take a look at `default-config.json`, which assumes `systemd` & `nginx`.

- `"branch"`: select the update branch. Supported values:
  - `"lts"` (currently, version 3)
  - `"unstable"` (currently, version 4)
  - `"dev"` (currently, version RC4)
- `"db_cnf_path"`: path to a `.my.cnf` file with database credentials able to use `mysqldump`
- `"db_name"`: name of the LimeSurvey database in MySQL/MariaDB
- `"db_port"`: port of the database server
- `"db_server"`: hostname or IP address of the database server
- `"install_octal_permissions"`: 755-style permissions applied to the newly-installed application files
- `"install_owner"`: `"username:group"` which should own the newly-installed application files
- `"install_path"`: path to the application files on the disk
- `"log_to_file"`: print the output of the script to a file
- `"log_to_stdout"`: print the output of the script to the console
- `"log_to_syslog"`: print the output of the script to local syslog
- `"web_server_init_system"`: select the init system used to restart the web server service. Supported values:
  - `"generic"`
  - `"systemd"`
  - `"service"`
  - `"init.d"`
  - `"openrc"`
  - `"rc.d"`
  - `"upstart"`
  - `"finit"`
  - `"epoch"`
- `"web_server_service"`: init/service name of the web server. Typically set to `apache2` or `nginx`.

### Running ls_updater

1. Prepare system to ensure the dependencies are met. For example, on Ubuntu 20.04:
    - `sudo apt install python3-pip mariadb-client`
    - `sudo python3 -m pip install bs4 requests wget`
3. `git pull https://github.com/xenago/ls_updater`
4. `cd ls_updater`
5. `nano .my.cnf` (only required if you don't already have one elsewhere - if you do, add its path to `config.json`)
6. `cp default-config.json config.json && nano config.json` (edit to include all necessary information, details below)
7. `sudo python3 ls_updater.py`

