import sys
import time
import config
from log import Log
import oracledb
from fr24sdk.client import Client
from fr24sdk.exceptions import (
    ApiError,
    AuthenticationError,
    Fr24SdkError,
)  # Import relevant exceptions

dbc: oracledb.Connection


def configure():  # load configuration file and parse args from command line
    global cfg
    cfg = config.Config(app_name="FlightRadar24 API")
    arg_prepare()
    cfg.parse()

    logger_file = cfg.get("", "logfile")
    if not logger_file:
        logger_file = cfg.mainpath(False) + "app.log"
    global app_log
    app_log = Log("app", log_file=logger_file, rewrite_file=False)
    global log
    log = app_log.get_logger()

    global config_file
    config_file = cfg.load(cfg.get("", "logf"))
    if cfg.error():
        log.error(cfg.get_result(True))
        sys.exit(cfg.get_result_code())
    else:
        log.info("Configuration from file: " + cfg.file_name)
        cfg.auto_save = True


def arg_prepare():  # command line argument definition
    cfg.prepare(
        [
            {
                "name_or_flags": ["--config", "-cfg"],
                "kwargs": {
                    "type": str,
                    "help": "Configuration file",
                    "required": False,
                },
            },
            {
                "name_or_flags": ["--logfile", "-log"],
                "kwargs": {"type": str, "help": "Log file name", "required": False},
            },
            {
                "name_or_flags": ["--airspace", "-asp"],
                "kwargs": {"type": str, "help": "FIC airspace(s)", "required": True},
            },
            {
                "name_or_flags": ["--full", "-fl"],
                "kwargs": {
                    "action": "store_true",
                    "help": "Full version",
                    "required": False,
                },
            },
            {
                "name_or_flags": ["--light", "-lt"],
                "kwargs": {
                    "action": "store_true",
                    "help": "Light version",
                    "required": False,
                },
            },
            {
                "name_or_flags": ["--hours", "-hrs"],
                "kwargs": {
                    "type": int,
                    "help": "Hours limit (0 = endless)",
                    "required": True,
                },
            },
            {
                "name_or_flags": ["--minutes", "-min"],
                "kwargs": {
                    "type": int,
                    "help": "Minutes interval (default 10)",
                    "required": True,
                },
            },
        ]
    )


def db_connect(connect):  # connect to database (for now only oracle)
    global dbc
    if connect:
        log.info(
            "Cnnecting to "
            + cfg.get("db", "engine")
            + " database => host: "
            + cfg.get("db", "host")
            + " service name: "
            + cfg.get("db", "service")
        )
        oracledb.init_oracle_client(lib_dir=cfg.get("db", "libdir"))
        try:
            dbc = oracledb.connect(
                user=cfg.get("db", "user"),
                password=cfg.get("db", "password"),
                host=cfg.get("db", "host"),
                port=cfg.get("db", "port"),
                service_name=cfg.get("db", "service"),
            )
            print(type(dbc))
            log.info("Connected to DB!")
        except Exception as e:
            log.error("Database " + cfg.get("db", "engine") + " problem " + str(e))
            sys.exit(str(e))
    else:
        if dbc is not None:
            try:
                log.info("Database disconnect")
                dbc.close()
            except Exception as e:
                log.error("Database " + cfg.get("db", "engine") + " problem " + str(e))


def insert_sql(
    data, add_fields: list
):  # make sql insert into table string from first data row and add-ons
    names = "INSERT INTO " + table_name + " ("
    values = " VALUES("
    counter = 1
    for row in data[:1]:  # row is list of tuples [(field_name, value object),...]
        for fld in row:
            names = names + fld[0] + ","
            values = values + f":{counter},"
            counter += 1
    for fld in add_fields:  # aadd_fields is list of tuples as same as row
        names = names + fld[0] + ","
        values = values + f":{counter},"
        counter += 1
    cmd = names[:-1] + ")" + values[:-1] + ")"
    return cmd


def insert_rows(
    data, add_fields: list
):  # transfers api data row to database value insert list + add-ons fields
    rows = []
    for row in data:
        lt = []
        for fld in row:
            lt.append(fld[1])
        for fld in add_fields:
            lt.append(fld[1])
        rows.append(lt)
    return rows


def data_mining():
    asp = cfg.get(
        "", "airspace"
    )  # all airspaces from config or command line like "LIMM,LIRR,LIBB"
    airspaces = asp.split(",")  # list of airspaces
    if airspaces:  # check of all airspaces FIC id's
        for fic in airspaces:
            if not fic:
                log.error("Airspace(s) parameter!")
                return
    else:
        log.error("Airspace(s) parameter!")
        return
    # prepare connection to api point (full or light version)
    log.info("FR24 API connection")
    full = cfg.get("", "full")
    version = "full" if full else "light"
    global table_name
    table_name = "FR24_LIVE_FLGT_POS_" + ("FL" if full else "LT")

    try:
        client = Client(api_token=cfg.get("api", "token"))
        if client:
            log.info("API connected!")
            sleep_interval = int(cfg.get("", "minutes")) * 60
            hours_limit = int(cfg.get("", "hours"))
            loop_count = -1000
            if hours_limit > 0:
                loop_count = int((hours_limit * 3600) / sleep_interval)
            log.info(
                f"Data mining Live Flight Positions {version.upper()}, airspaces {airspaces} : with {sleep_interval} seconds interval."
                + (f" Period {hours_limit} hour(s).")
                if hours_limit > 0
                else ""
            )
            while loop_count != 0:
                if loop_count != 0:
                    for airspace in airspaces:
                        log.info(f"   FIC airspace region <<< {airspace} >>>")
                        api_result = None
                        try:
                            if full:
                                api_result = client.live.flight_positions.get_full(
                                    airspaces=[airspace]
                                )
                            else:
                                api_result = client.live.flight_positions.get_light(
                                    airspaces=[airspace]
                                )

                            if api_result.data:
                                add_list = [("region", airspace.upper())]
                                sql_cmd = insert_sql(api_result.data, add_list)
                                sql_data = insert_rows(api_result.data, add_list)

                                with dbc.cursor() as cursor:
                                    cursor.prepare(sql_cmd)
                                    cursor.executemany(None, sql_data)
                                    log.info(
                                        f"      DB inserted rows : {cursor.rowcount}"
                                    )
                                dbc.commit()
                                time.sleep(1)
                            else:
                                log.error("API problem NO DATA!")

                        except AuthenticationError:
                            log.error(
                                "Authentication failed. Please check your API token."
                            )
                            loop_count = 0
                        except ApiError as e:
                            log.error(
                                f"API Error occurred: Status {e.status}, Message: {e.message}"
                            )
                            log.error(f"Request URL: {e.request_url}")
                            if e.body:
                                log.error(f"Response body: {e.body}")
                            loop_count = 0
                        except Fr24SdkError as e:
                            log.error(f"An SDK-specific error occurred: {e}")
                            loop_count = 0
                        except Exception as e:
                            log.error(f"An unexpected error occurred: {e}")
                            loop_count = 0

                    if loop_count != -1000 and loop_count != 0:
                        loop_count -= 1
                    msg = f"Waiting {sleep_interval} seconds."
                    if loop_count > 0:
                        msg = msg + " " + str(loop_count) + " loops remainig."
                    if loop_count != 0:
                        log.info(msg)
                        time.sleep(sleep_interval)

        else:
            log.error("API problem : connection refused!")
    except Exception as a:
        log.error("API problem " + str(a))


def main():
    configure()
    db_connect(True)
    data_mining()
    db_connect(False)
    app_log.close()


if __name__ == "__main__":
    main()
