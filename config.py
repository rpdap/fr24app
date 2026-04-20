import sys
import configparser
import argparse
import os.path
from collections import OrderedDict

DEFAULT_SECTION = "app"
SORT_GROUPS = 2
SORT_NAMES = 4


class Config:
    def __init__(self, app_name=None):
        self.app_path = self.mainpath(False)
        self.app_name = self.mainpath(True)
        self.cfg_parser = configparser.ConfigParser()
        self.changed = False
        self.auto_save = False
        self.sorted = SORT_GROUPS + SORT_NAMES  # sorting sections and items
        self.result = {
            "code": 0,
            "message": "",
        }  # resul code and message (errno, strerror)
        self.arg_parser = argparse.ArgumentParser(
            prog=self.mainpath(False) if app_name is None else app_name
        )

    def mainpath(self, full=False):
        file_name = sys.argv[0].replace("\\", "/")
        if full:
            return file_name
        else:
            return file_name[: file_name.rfind("/") + 1]

    def prepare(self, arguments_to_add):
        for arg in arguments_to_add:
            self.arg_parser.add_argument(*arg["name_or_flags"], **arg["kwargs"])

    def find_ini_par(self, argv):
        for par in argv:
            up = par.upper()
            if "-CFG" in up or "-INI" in up:
                return par.partition("=")[2]
        return ""

    def parse(self):
        self.args = self.arg_parser.parse_args()

    def error(self):
        return self.result["code"] != 0

    def set_result(self, code, msg):
        self.result["code"] = code
        self.result["message"] = msg

    def get_result(self, as_string=False):
        if as_string:
            return f"code: {self.result['code']}, mesage: {self.result['message']}"
        else:
            return self.result

    def get_result_code(self):
        return self.result["code"]

    def get_result_msg(self):
        return self.result["message"]

    def get(self, section_name, id):
        value = ""
        if not self.error():
            try:
                if not section_name:
                    section_name = DEFAULT_SECTION
                value = self.cfg_parser.get(section_name, id)
            except Exception:
                value = ""
        if not value:
            try:
                value = getattr(self.args, id)
            except AttributeError:
                value = ""
        return value

    def get_full(self, section_name, id):
        ret = self.get(section_name, id)
        if ret != "":
            ret = section_name + "." + ret
        return ret

    def get_id(self, id):
        value = self.get(DEFAULT_SECTION, id)
        if value:
            return [id + "=" + value]
        else:
            IL = []
            for section in self.cfg_parser.sections():
                for key, value in self.cfg_parser[section].items():
                    if key == id:
                        IL.append(section + "." + key + "=" + value)
            return IL

    def get_group(self, section_name, full):
        ret = []
        if self.cfg_parser.has_section(section_name):
            for key, value in sorted(self.cfg_parser.items(section_name)):
                if full:
                    ret.append(section_name + "." + key + "=" + value)
                else:
                    ret.append(key + "=" + value)
        return ret

    def set_sort_groups(self, set_sorted):
        if set_sorted:
            self.sorted = self.sorted | SORT_GROUPS
        else:
            self.sorted = self.sorted ^ SORT_GROUPS

    def set_sort_names(self, set_sorted):
        if set_sorted:
            self.sorted = self.sorted | SORT_NAMES
        else:
            self.sorted = self.sorted ^ SORT_NAMES

    def set(self, section_name, id, value):
        if not section_name:
            section_name = DEFAULT_SECTION
        if not self.cfg_parser.has_section(section_name):
            self.cfg_parser.add_section(section_name)
        self.cfg_parser.set(section_name, id, value)
        self.changed = True
        if self.auto_save:
            self.save()

    def remove(self, section_name, id):
        if not section_name:
            section_name = DEFAULT_SECTION
        self.cfg_parser.remove_option(section_name, id)
        if self.auto_save:
            self.save()

    def remove_group(self, section_name):
        if section_name and self.cfg_parser.has_section(section_name):
            self.cfg_parser.remove_section(section_name)
            if self.auto_save:
                self.save()

    def sort(self):
        if self.sorted & SORT_GROUPS > 0:
            self.cfg_parser._sections = OrderedDict(
                sorted(self.cfg_parser._sections.items(), key=lambda t: t[0])
            )
        if self.sorted & SORT_NAMES == SORT_NAMES:
            scl = configparser.ConfigParser()
            scl.read_dict(self.cfg_parser)
            self.cfg_parser = configparser.ConfigParser()
            for section in scl.sections():
                self.cfg_parser.add_section(section)
                for key, value in sorted(scl.items(section)):
                    self.cfg_parser.set(section, key, value)

    def load(self, file_name):
        try:
            if not file_name:
                file_name = self.app_path + "app.ini"
                if not os.path.isfile(file_name):
                    file_name = self.app_name[: self.app_name.rfind(".") + 1] + "ini"
            with open(file_name) as f:
                self.cfg_parser.read_file(f)
                self.file_name = file_name
                self.changed = True
        except IOError as e:
            self.set_result(
                e.errno,
                (e.strerror or "") + " -> " + file_name,
            )

    def save_to(self, file_name):
        wf = self.file_name
        try:
            with open(wf, "w") as f:
                self.sort()
                self.cfg_parser.write(f)
                self.file_name = file_name
        except IOError as e:
            self.set_result(
                e.errno,
                (e.strerror or "") + " -> " + file_name,
            )

    def save(self):
        if self.changed:
            self.save_to(self.file_name)
            self.changed = False
