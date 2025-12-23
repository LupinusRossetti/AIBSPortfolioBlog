from PIL import Image
import os

path = r"c:\LupinusPrivate\portfolio\images\image\Decorations\divider_lace_2.png"
if os.path.exists(path):
    with Image.open(path) as img:
        print(f"Lace Dimensions: {img.width}x{img.height}")
else:
    print("File not found")
