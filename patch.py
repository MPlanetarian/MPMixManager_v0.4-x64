with open("Mix_Archive_Manager.sh", "r") as f:
    lines = f.readlines()

new_lines = []
replaced = False

new_block = '''3|liquid|liquid-glass|glass) 
    if [ "$(uname -s)" = "Darwin" ]; then
        ./venv/bin/python scripts/MP_Audio_Player_Liquid_Glass_OpenGL_macOS.py >/dev/null 2>&1 &
    else
        ./scripts/launch-liquid-glass >/dev/null 2>&1 &
    fi
    _MENU_FRAME_FRESH=0 
    ;;
'''

for line in lines:
    if ('3|' in line and 'liquid' in line) or ('liquid' in line and 'glass' in line):
        new_lines.append(new_block)
        replaced = True
    else:
        new_lines.append(line)

if replaced:
    with open("Mix_Archive_Manager.sh", "w") as f:
        f.writelines(new_lines)
    print("Successfully patched Option 3!")
else:
    print("Still couldn't find it. Here are all lines in the file containing '3':")
    for line in lines:
        if '3' in line:
            print(repr(line.strip()))
