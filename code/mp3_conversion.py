import os

"""
https://ms3.readthedocs.io/en/latest/install.html

MusicXML -> MP3 batch conversion using 'ms3 parsing' in command line

Install via pip: 
python3 -m pip install ms3

ms3 convert -d input_dir -o output_dir --format output_format --extensions ['input_format1, input_format2, ...']
e.g. ms3 convert -d test/ms3_test -o test/ms3_test/outputs --format mp3 --extensions ['mxl']
"""
def convert_mxl_to_mp3(input_directory, output_directory, input_formats=['mxl'], output_format='mp3'):
    command = f"ms3 convert -d {input_directory} -o {output_directory} --format {output_format} --extensions {input_formats}"
    os.system(command)


input_directory = 'test/ms3_test'

# check if the directories exists
if not os.path.exists(input_directory):
    print('Input directory does not exist')
    exit(1)

# check if outputs folder exists in the input directory
if not os.path.exists(f'{input_directory}/outputs'):
    os.makedirs(f'{input_directory}/outputs')
    print('Created outputs folder in the input directory')

output_directory = f'{input_directory}/outputs'



convert_mxl_to_mp3(input_directory, output_directory)


