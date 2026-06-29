import sys
import configparser
import argparse
import os.path
import base64

DEFAULT_SECTION = "app"
SORT_GROUPS = 2
SORT_NAMES = 4

MP_NAME = 2
MP_PATH = 4


class Config:
    def __init__(self, app_name=None):
        self.app_path = self.mainpath(MP_PATH)  # application path
        self.app_name = self.mainpath(MP_NAME)  # application name without path
        self.cfg_parser = configparser.ConfigParser()  # parser init
        self.changed = False  # true if parameters list changed
        self.auto_save = False  # set autosave after change
        self.sorted = SORT_GROUPS + SORT_NAMES  # sorting sections and items
        self.result = {  # result dict record
            "code": 0,
            "message": "Ok ",
        }  # resul code and message (errno, strerror)
        self.arg_parser = argparse.ArgumentParser(  # arguments parsing
            prog=self.app_name if app_name is None else app_name
        )

    def mainpath(
        self, type: int
    ):  # returns application path (MP_PATH) or name (MP_NAME) or both (MP_PATH + MP_NAME)
        file_name = sys.argv[0].replace("\\", "/")
        rp: str = ""
        if type & MP_PATH > 0:
            rp = rp + file_name[: file_name.rfind("/") + 1]
        if type & MP_NAME > 0:
            rp = rp + file_name[file_name.rfind("/") + 1 :]
        return rp

    def prepare(
        self,
        arguments_to_add: list,  # list of arguments definition (each argument id dictionary)
    ):
        for arg in arguments_to_add:
            self.arg_parser.add_argument(*arg["name_or_flags"], **arg["kwargs"])

    def parse(self):  # parse prepared arguments with commandline args
        self.args = self.arg_parser.parse_args()

    def error(self):  # return Treu if cone != 0
        return self.result["code"] != 0

    def set_result(self, code, msg):
        self.result["code"] = code
        self.result["message"] = msg

    def get_result(self, as_string=False):
        if as_string:
            return f'code: {self.result["code"]}, mesage: "{self.result["message"]}"'
        else:
            return self.result

    def get_result_code(self):
        return self.result["code"]

    def get_result_msg(self):
        return self.result["message"]

    def encode_decode(self, data: str, enc: bool):
        if data:
            if data.startswith("~") or enc:
                pw = ")tReb0rK83lP(*)"
                if data.startswith("~"):
                    data = data[1:]
                    data = base64.b64decode(data).decode()

                cp = (pw * (len(data) // len(pw) + 1))[: len(data)]
                data = "".join(chr(ord(c) ^ ord(p)) for c, p in zip(data, cp))
                if enc:
                    return "~" + base64.b64encode(data.encode()).decode()
                else:
                    return data
        return data

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
        return self.encode_decode(value, False)  # last check if param neds decrypt (~)

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

    def set(self, section_name, id, value: str):
        if not section_name:
            section_name = DEFAULT_SECTION
        if not self.cfg_parser.has_section(section_name):
            self.cfg_parser.add_section(section_name)
        if value.startswith("~"):
            value = self.encode_decode(value[1:], True)
        self.cfg_parser.set(section_name, id, value)
        self.changed = True
        if self.auto_save:
            self.save()

    def set_crypted(self, section_name, id, value):
        self.set(section_name, id, self.encode_decode(value, True))

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
            # Sort sections and recreate the parser
            sorted_sections = sorted(self.cfg_parser.sections())
            new_parser = configparser.ConfigParser()
            for section in sorted_sections:
                new_parser.add_section(section)
                # Sort options within sections if SORT_NAMES is set
                if self.sorted & SORT_NAMES == SORT_NAMES:
                    sorted_items = sorted(self.cfg_parser.items(section))
                    for key, value in sorted_items:
                        new_parser.set(section, key, value)
                else:
                    for key, value in self.cfg_parser.items(section):
                        new_parser.set(section, key, value)
            self.cfg_parser = new_parser
        elif self.sorted & SORT_NAMES == SORT_NAMES:
            # Only sort options within existing sections
            new_parser = configparser.ConfigParser()
            for section in self.cfg_parser.sections():
                new_parser.add_section(section)
                sorted_items = sorted(self.cfg_parser.items(section))
                for key, value in sorted_items:
                    new_parser.set(section, key, value)
            self.cfg_parser = new_parser

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

    def close(self):
        self.save()
