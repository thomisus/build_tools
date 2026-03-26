#!/usr/bin/env python

import sys
sys.path.append('../../scripts')
import base
import os
import glob
import imagesize
import importlib.util
from pathlib import Path
from os.path import dirname, abspath, join

# Python 3 compatibility hack
try:
    unicode('')
except NameError:
    unicode = str


params = sys.argv[1:]

if (5 != len(params)):
  print("use: thumbnails.py path_to_builder_directory path_to_input_files_directory path_to_output_files_directory width height")
  exit(0)

mapping = {"[512x724]": "inside_1x_[512x724]",
        "[1024x1448]": "inside_2x_[1024x1448]",
        "[228x316]": "main_1x_[228x316]",
        "[456x632]": "main_2x_[456x632]",
        "[256x368]": "mobile_[256x368]",
        "[792x1098]": "source_[792x1098]",
        "[324x458]": "main_1x_[324x458]",
        "[648x916]": "main_2x_[648x916]",
		"[400x566]": "pop_up_[400x566]",
        "[184x260]": "desktop[184x260]",
}

cur_path = os.getcwd()
base.configure_common_apps()

directory_x2t = params[0].replace("\\", "/")
directory_input = params[1].replace("\\", "/")
directory_output = params[2].replace("\\", "/")
th_width = params[3]
th_height = params[4]

docbuilder_path = os.path.join(directory_x2t, "docbuilder.py")
if not os.path.isfile(docbuilder_path):
    print(f"ERROR: docbuilder.py not found in '{directory_x2t}'")
    exit(1)

spec = importlib.util.spec_from_file_location("docbuilder", docbuilder_path)
docbuilder_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(docbuilder_mod)

CDocBuilder      = docbuilder_mod.CDocBuilder
CDocBuilderValue = docbuilder_mod.CDocBuilderValue

#output_dir = directory_output + "/[" + str(th_width) + "x" + str(th_height) + "]"
#if base.is_dir(output_dir):
#  base.delete_dir(output_dir)
#base.create_dir(output_dir)

input_files = []
for file in glob.glob(os.path.join(u"" + directory_input, u'*')):
  input_files.append(file.replace("\\", "/"))

#print(input_files)
temp_dir = os.getcwd().replace("\\", "/") + "/temp"
if base.is_dir(temp_dir):
  base.delete_dir(temp_dir)
base.create_dir(temp_dir)

directory_fonts = directory_x2t + "/sdkjs/common"
if not base.is_file(directory_fonts + "/AllFonts.js"):
  base.cmd_in_dir(directory_x2t, "docbuilder", [], True)

# # True for fit, False for 100%
# isScaleSheetToPage = False
#
# json_fit_text = "0"
# if isScaleSheetToPage:
#   json_fit_text = "1"
#
# #json_params += "'fitToWidth':" + json_fit_text + ",'fitToHeight':" + json_fit_text + ","
# if isScaleSheetToPage:
#   json_params = "{'spreadsheetLayout':{'fitToWidth':1,'fitToHeight':1},"
# else:
#   json_params = "{'spreadsheetLayout':{'fitToWidth':0,'fitToHeight':0},"
# json_params += "'documentLayout':{'drawPlaceHolders':true,'drawFormHighlight':true,'isPrint':true}}"
# json_params = json_params.replace("'", "&quot;")


json_params = "{"

json_params += "'spreadsheetLayout':{"

# True for fit, False for 100%
isScaleSheetToPage = False

json_fit_text = "0"
if isScaleSheetToPage:
  json_fit_text = "1"

json_params += "'fitToWidth':" + json_fit_text + ",'fitToHeight':" + json_fit_text + ","

if True:
  json_params += "'orientation':'landscape',"

page_margins = "'pageMargins':{'bottom':10,'footer':5,'header':5,'left':5,'right':5,'top':10}"
page_setup = "'pageSetup':{'orientation':1,'width':210,'height':297,'paperUnits':0,'scale':190," \
             "'printArea':false,'horizontalDpi':600,'verticalDpi':600,'usePrinterDefaults':true,'fitToHeight':1,'fitToWidth':1}"

json_params += "'sheetsProps':{'0':{'headings':false,'printTitlesWidth':null,'printTitlesHeight':null," + page_margins + "," + page_setup + "}}},"

json_params += "'documentLayout':{'drawPlaceHolders':true,'drawFormHighlight':true,'isPrint':true},"
json_params += "'ignorePrintArea':'false'"
json_params += "}"
json_params = json_params.replace("'", "&quot;")

if not os.path.exists(directory_output):
  os.mkdir(directory_output)

output_len = len(input_files)
output_cur = 1
for input_file in input_files:
  if os.path.isdir(input_file):
    next_dir_name = os.path.basename(input_file)
    base.cmd("python", ["thumbnails_old.py", directory_x2t, input_file, os.path.join(directory_output, next_dir_name), th_width, th_height])
    if base.is_dir(temp_dir):
      base.delete_dir(temp_dir)
    base.create_dir(temp_dir)
    continue
  print("process [" + str(output_cur) + " of " + str(output_len) + "]: " + str(input_file.encode("utf-8")))

  width_page = th_width
  height_page = th_height

  json_params_file = json_params

  if input_file.lower().endswith('.xlsx'):
    temp_dir_builder = directory_output + "/temp_builder"
    if base.is_dir(temp_dir_builder):
      base.delete_dir(temp_dir_builder)
    base.create_dir(temp_dir_builder)
    builder = CDocBuilder()
    builder.SetTmpFolder(temp_dir_builder)

    builder.OpenFile(input_file)
    context = builder.GetContext()
    globalObj = context.GetGlobal()

    cmd = """
(function(){
Api.getPrintAreaSize = function() {
  return { Width:0, Height:0 };
};
var sheet = Api.GetSheets()[0];
var usedRange = sheet.GetUsedRange();

var maxCol = -1;
var maxRow = -1;
usedRange.ForEach(function (cell) {
    if (cell.GetRowHeight() === 0 || cell.GetColumnWidth() === 0) {
        return;
    }
    var row0 = cell.GetRow() - 1;
    var col0 = cell.GetCol() - 1;
    var hasContent = false;
    var val = cell.GetValue();
    if (val !== "" && val !== null && val !== undefined) {
        hasContent = true;
    }
    if (!hasContent) {
        var formula = cell.GetFormula();
        if (typeof formula === 'string' && formula.indexOf("=") === 0) {
            hasContent = true;
        }
    }
    if (hasContent) {
        if (col0 > maxCol) maxCol = col0;
        if (row0 > maxRow) maxRow = row0;
    }
});
if (maxRow < 0 || maxCol < 0) {
    return;
}
var printRange = sheet.GetRange(
    sheet.GetRangeByNumber(0, 0),
    sheet.GetRangeByNumber(maxRow, maxCol)
);
Api.getPrintAreaSize = function() {
  return { Width:printRange.Width, Height:printRange.Height };
};})();
"""

    builder.ExecuteCommand(cmd)
    api = globalObj['Api']

    sizeWH = api.getPrintAreaSize()
    wPrint = sizeWH.Get("Width").ToDouble()
    hPrint = sizeWH.Get("Height").ToDouble()

    print("CELL (printSize): " + str(wPrint) + "x" + str(hPrint))

    if (wPrint > 1 and hPrint > wPrint):
      tmp = width_page
      width_page = height_page
      height_page = tmp
      json_params_file = json_params_file.replace("&quot;width&quot;:210,&quot;height&quot;:297", "&quot;width&quot;:297,&quot;height&quot;:210")

    builder.CloseFile()
    base.delete_dir(temp_dir_builder)

  output_dir = os.path.join(directory_output,
                            os.path.splitext(os.path.basename(input_file))[0])
  #output_dir = str(output_dir.encode("utf8"))
  output_dir = abspath(unicode(output_dir))
  if not os.path.exists(output_dir):
    os.mkdir(output_dir)
  output_dir = os.path.join(output_dir,
                            mapping["[" + str(th_width) + "x" + str(th_height) + "]"])
  #output_dir = str(output_dir.encode("utf8"))
  #output_dir = dirname(abspath(unicode(output_dir)))
  output_dir = abspath(unicode(output_dir))
  if not os.path.exists(output_dir):
    os.mkdir(output_dir)
  output_file = output_dir # os.path.join(output_dir, os.path.splitext(os.path.basename(input_file))[0])
  xml_convert = u"<?xml version=\"1.0\" encoding=\"UTF-8\"?>"
  xml_convert += u"<TaskQueueDataConvert>"
  xml_convert += (u"<m_sFileFrom>" + input_file + u"</m_sFileFrom>")
  xml_convert += (u"<m_sFileTo>" + output_file + u".zip</m_sFileTo>")
  xml_convert += u"<m_nFormatTo>1029</m_nFormatTo>"
  xml_convert += (u"<m_sAllFontsPath>" + directory_fonts + u"/AllFonts.js</m_sAllFontsPath>")
  xml_convert += (u"<m_sFontDir>" + directory_fonts + u"</m_sFontDir>")
  xml_convert += (u"<m_sJsonParams>" + json_params_file + u"</m_sJsonParams>")
  xml_convert += u"<m_nDoctParams>1</m_nDoctParams>"
  xml_convert += u"<m_oThumbnail>"
  xml_convert += u"<first>false</first>"

  if ((0 != width_page) and (0 != height_page)):
    xml_convert += u"<aspect>16</aspect>"
    xml_convert += (u"<width>" + str(width_page) + u"</width>")
    xml_convert += (u"<height>" + str(height_page) + u"</height>")
  xml_convert += u"</m_oThumbnail>"
  xml_convert += u"<m_nDoctParams>1</m_nDoctParams>"
  xml_convert += (u"<m_sTempDir>" + temp_dir + u"</m_sTempDir>")
  xml_convert += u"</TaskQueueDataConvert>"
  base.save_as_script(temp_dir + "/to.xml", [xml_convert])
  base.cmd_in_dir(directory_x2t, "x2t", [temp_dir + "/to.xml"], True)
  base.delete_dir(temp_dir)
  base.create_dir(temp_dir)
  base.extract_unicode(output_file + u".zip", output_file)
  if os.path.exists(output_file + ".zip"):
    try:
      base.delete_file(output_file + ".zip")
    except:
      print("Error in deletin file: ", output_file + ".zip")
  output_cur += 1
  #output_file = output_file.replace("\\", "/")
  #imnames = Path(output_file).glob("*.png")#glob.glob("/" + output_file.replace(":", "") + "/*.png")
  imnames = [str(pp) for pp in Path(output_file).glob("*.png")]
  #print(output_file + "/*.png", imnames)
  #continue
  if len(imnames) == 0:
    base.delete_dir(output_file)
  else:
    width, height = imagesize.get(imnames[0])
    print("WxH: ", width, height)
    if width < height and False: #удалить вертикальные превью
      base.delete_dir(output_file)

base.delete_dir(temp_dir)
os.chdir(cur_path)