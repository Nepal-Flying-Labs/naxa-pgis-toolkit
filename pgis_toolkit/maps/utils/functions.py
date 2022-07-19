import os
import shutil


#function to clear files in a specific directory
def clear_dir(dir):
    for files in os.listdir(dir):
        path = os.path.join(dir, files)
        try:
            shutil.rmtree(path) #clearing directory
            os.rmdir(dir) #removing directory
        except OSError:
            os.remove(path)
