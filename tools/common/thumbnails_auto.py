#!/usr/bin/env python

import sys
sys.path.append('../../scripts')
import base
import os
import glob
from pathlib import Path

params = sys.argv[1:]

if (3 != len(params)):
  print("use: thumbnails_auto.py path_to_builder_directory path_to_input_files_directory path_to_output_files_directory")
  exit(0)

base.configure_common_apps()

directory_x2t = params[0].replace("\\", "/")
directory_input = params[1].replace("\\", "/")
directory_output = params[2].replace("\\", "/")


if not os.path.exists(directory_output):
  os.mkdir(directory_output)

def rename_dir(input, output):
  if base.is_dir(u"" + directory_output + u"/" + output):
    base.delete_dir(u"" + directory_output + u"/" + output)
  os.rename(u"" + directory_output + u"/" + input, u"" + directory_output + u"/" + output)
  return

base.cmd("python", ["thumbnails_old.py", directory_x2t, directory_input, directory_output, "512", "724"])
base.cmd("python", ["thumbnails_old.py", directory_x2t, directory_input, directory_output, "1024", "1448"])
base.cmd("python", ["thumbnails_old.py", directory_x2t, directory_input, directory_output, "324", "458"])
base.cmd("python", ["thumbnails_old.py", directory_x2t, directory_input, directory_output, "648", "916"])
base.cmd("python", ["thumbnails_old.py", directory_x2t, directory_input, directory_output, "256", "368"])

base.cmd("python", ["thumbnails_old.py", directory_x2t, directory_input, directory_output, "400", "566"])
base.cmd("python", ["thumbnails_old.py", directory_x2t, directory_input, directory_output, "184", "260"])
#base.cmd("python", ["thumbnails.py", directory_x2t, directory_input, directory_output, "792", "1098"])

#rename_dir("[512x724]", "inside_1x_[512x724]")
#rename_dir("[1024x1448]", "inside_2x_[1024x1448]")
#rename_dir("[228x316]", "main_1x_[228x316]")
#rename_dir("[456x632]", "main_2x_[456x632]")
#rename_dir("[256x368]", "mobile_[256x368]")
#rename_dir("[792x1098]", "source_[792x1098]")

dirnames = list(Path(directory_output).iterdir())
for dir_name in dirnames:
  if len(list(Path(dir_name).iterdir())) == 0:
    print("Delete dir ", dir_name)
    Path(dir_name).rmdir()
    #base.delete_dir(dir_name)
