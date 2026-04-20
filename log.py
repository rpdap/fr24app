import logging
import sys
import os


class Log:
    def __init__(self, name, log_file, level=logging.INFO, rewrite_file=False):

        if rewrite_file or not os.path.isfile(log_file):
            try:
                with open(log_file, "w") as f:
                    f.write(
                        "timestamp               | name       | level    | message\n"
                    )
                rewrite_file = False
            except IOError as e:
                print(e.errno, (e.strerror or ""))

        logging.basicConfig(
            filename=log_file,
            level=level,
            format="%(asctime)s | %(name)-10s | %(levelname)-8s | %(message)s",
            filemode="a",
        )

        formatter = logging.Formatter(
            "{asctime} | {levelname:8} | {message}", style="{"
        )

        self.logger = logging.getLogger(name)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)

        self.logger.info("<<< s-t-a-r-t >>>")

    def get_logger(self):
        return self.logger

    def close(self):
        self.logger.info("<<< s-t-o-p >>>\n")
        for handler in self.logger.handlers:
            handler.flush()
            handler.close()
            self.logger.removeFilter(handler)
