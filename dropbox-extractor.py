import dropbox
import io
from PyPDF2 import PdfReader
import requests
import base64
import extractor_config


## Global variables defined in extractor_config.py ##

# This is a base64 string encoding of an image you wish to ignore when extracting images. This is likely a company logo or something else not needed
logo_string = extractor_config.logo_string

# Keys/Secrets/Tokens for the Dropbox API
DROPBOX_APP_KEY = extractor_config.DROPBOX_APP_KEY
DROPBOX_APP_SECRET = extractor_config.DROPBOX_APP_SECRET
DROPBOX_REFRESH_TOKEN = extractor_config.DROPBOX_REFRESH_TOKEN

# Dropbox path you want to start in
dropbox_root_path = extractor_config.dropbox_root_path

# This is used to search for image files, png/jpg/jpeg are the only ones we will likely see so that's all I've entered here
imageExts = extractor_config.imageExts


## Global variables ##

# These are just here to declare files and imageFiles as arrays for use later
files = []
imageFiles = []

#### END GLOBAL VARIABLES ####



# I've made this script very modular to make testing and troubleshooting easier.
# There are a few functions that are only called once and would probably be better off just being coded in the main routine
# but if the scope of work ever changes it might be better to have the functions instead

def getPDFLink(path):
    # opens the given pdf path and returns a string
    pdfFile = dbx.files_get_temporary_link(path)
    
    if pdfFile.link:
        data = io.BytesIO(requests.get(pdfFile.link).content)
        return data
    else:
        print("Could not download file.. skipping..")
        return None

def extractImages(reader):
    # accepts a pypdf2 reader object, then parses it for images.
    # if one or more images are found it will return an array of img data
    # otherwise it will return 0 to signify no images found
    imgArr = []
    for page in reader.pages:
        for image_file_object in page.images:
            if compareBase64(logo_string, base64.b64encode(image_file_object.data)) == 0:
                f = io.BytesIO(image_file_object.data)
                imgArr.append(f)
    return imgArr

def uploadImages(path, imgArr, dt=None):
    # Accepts a dropbox folder path, an array of images, and optionally a datetime argument
    # if a datetime argument is supplied (dt) then the uploaded images will have their datetime modified to match dt argument
    i = 1
    for img in imgArr:
        new_img_file_path = path + "/" + str(i) + ".jpeg"
        if dt:
            dbx.files_upload(img.read(), new_img_file_path, client_modified=dt)
            i += 1
        else:
            dbx.files_upload(img.read(), new_img_file_path)
            i += 1

def getFolders(path):
    # Accepts a folder path and will return an array of folders paths that were inside the root folder provided here
    folderArr = []
    response = dbx.files_list_folder(path=path)
    for item in response.entries:
        if isinstance(item, dropbox.files.FolderMetadata):
            folderArr.append(item)
    return folderArr


def getFiles(path):
    # Accepts a folder path and will return an array of file paths that were inside the root folder provided here
    fileArr = []
    response = dbx.files_list_folder(path=path)
    for item in response.entries:
        if isinstance(item, dropbox.files.FileMetadata):
            fileArr.append(item)
    return fileArr


def folderHasImages(fileArr):
    # accepts an array of file data, and then checks to see if they are images or not
    # it will return 1 on the first image it sees
    # if it never sees an image it will return 0
    for item in fileArr:
        for ext in imageExts:
            if item.name.endswith(ext):
                return 1
    return 0

def folderHasPDF(fileArr):
    # accepts an array of file data, and then checks to see if any of them are PDFs or not
    # it will return 1 on the first PDF it sees
    # if it never sees a PDF it will return 0
    for item in fileArr:
        if item.name.endswith(".pdf"):
            return 1
    return 0

def getMetaData(path):
    metadata = dbx.files_get_metadata(path)
    return metadata

def getPDF(fileArr):
    # accepts an array of file data, and returns the path of the pdf file in the array
    # if it finds only 1 pdf file it will return the path
    # if it finds more than 1 pdf file it will return -1, because there isn't a defined way of handling that at the moment
    # if it does not find a pdf file then it will return 0
    pdfCount = 0
    for item in fileArr:
        if item.name.endswith(".pdf"):
            pdfCount += 1
            pdfPath = item.path_display
    if pdfCount == 1:
        return pdfPath
    elif pdfCount == 0:
        return 0
    elif pdfCount > 1:
        return -1
    else:
        return 0


def getClientDatetime(pdf):
    # accepts a pdf path and returns the client_modified meta data if it exists
    # if it doesn't exist (it always should) this will return 0
    metadata = dbx.files_get_metadata(pdf)
    if metadata:
        return metadata.client_modified
    else:
        return None


def newFileCheck(fileArr, dt):
    # Accepts a datetime argument, then it will check the datetimes of the files in the file arr
    # if all of the datetimes match the provided dt argument, then it will return 0
    # if ANY of the file datetimes don't match the provided datetime, then it will return 1
    datetimes = []

    for file in fileArr:
        datetimes.append(file.client_modified)

    for dts in datetimes:
        if dts != dt:
            return 1
    return 0


def compareBase64(code1, code2):
    # accepts 2 base64 strings and compared them to see if they are the same
    # If they are the same then it returns 1
    # otherwise it returns 0
    if code1 == code2:
        return 1
    else:
        return 0


# def folderExist(path):
#     # This was going to be here when extracting txt data from the PDFs and then creating a new folder
#     # But for the current scope of work this is not needed
#     pass

def removeImages(fileArr):
    # Accepts an array of file paths and will delete all files matching the ext list (see global variable at top of script). 
    for file in fileArr:
        for ext in imageExts:
            if file.name.endswith(ext):
                dbx.files_delete(file.path_display)
                break





# main section
# First we enter our token/keys/secrets to auth with Dropbox when calling api calls
dbx = dropbox.Dropbox(
            app_key = DROPBOX_APP_KEY,
            app_secret = DROPBOX_APP_SECRET,
            oauth2_refresh_token = DROPBOX_REFRESH_TOKEN)

# Now let's get a list of all of the folders inside the root folder
rootFolderArr = getFolders(dropbox_root_path)

# next let's iterate through each folder inside of the root folder
for folder in rootFolderArr:
    try:
        # CurrentDir is a bit easier to read than "folder.path_display", this is just here for ease of reading
        currentDir = folder.path_display
        
        # Let's now get a list of all of the files in the current folder
        fileArr = getFiles(folder.path_display)

        # First we check to see if the folder has a pdf
        pdfpath = getPDF(fileArr)
        

        if pdfpath: # if pdfpath has data (aka isn't 0 or -1) then we have a single pdf in the folder and now have the path saved to pdfpath
            dt = getClientDatetime(pdfpath)    # Now let's get the the client_modifed datetime from the pdf. We will need the dt variable later!!

            if dt is None:
                # We HAVE to have this later to upload files with the correct datetime, so if this is None then we will just skip the folder
                print("Could not get datetime from file.. skipping this folder..")
                continue

            # let's open the pdf and get ready to extract data
            # getPDFData outputs a pyPDF2 reader object, so I've kept the variable name the same for clarity
            data = getPDFLink(pdfpath)

            # Let's make sure the data returned from the getPDFLink function is there, if not then we can't do anything with this file and will have to skip this folder
            if data is None:
                # Skip the folder and move on to the next one
                print("Could not get a link to download this file.. skipping this folder..")
                continue

            # data variable has data, let's keep moving on with this folder
            reader = PdfReader(data)

            # If it does has a pdf, let's see if it has any images
            if folderHasImages(fileArr):

                # If it does have one or more images, then let's check the file datetimes to see if the PDF has been updated
                if newFileCheck(fileArr, dt): # checks to see if the client_modified dates match, if not then the PDF was probably updated and needs to be re-extracted

                    # if the PDF is newer than the images, we delete the images and then re-extract them
                    print(folder.path_display, "has a pdf older than the images, removing images and re-extracting...")
                    imgArr = extractImages(reader)
                    removeImages(fileArr)
                    print("removed images.. now uploading new images")
                    uploadImages(currentDir, imgArr, dt)
                # if the PDF file isn't newer than the images, we leave the folder alone
                else:
                    print(folder.path_display, "has images, skipping this folder...")

            # if the folder has a PDF but no images, we need to extract images
            else:
                print("Extracting images from", pdfpath)
                imgArr = extractImages(reader)
                if imgArr:
                    dt = getClientDatetime(pdfpath)
                    uploadImages(currentDir, imgArr, dt)
                else:
                    print("imgArr has 0 entires, pdf likely does not have any images")

        # If the folder does NOT have a PDF, then there's no point in doing anything here
        elif pdfpath == 0:
            print("no pdf found.. skipping {folder.path_display} folder.")

        # If the folder has more than 1 PDF then I'm not sure what to do so we are going to skip it
        elif pdfpath == -1:
            print("more than 1 pdf found. Skipping folder..")
        else:
            print("I'm not sure how you got here, I'm not sure what kind of terrible thing you did to get this message")

    except Exception as e: print(e)
