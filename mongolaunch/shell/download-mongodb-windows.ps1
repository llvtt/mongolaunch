# Download MongoDB
$webClient = New-Object System.Net.WebClient
$webClient.DownloadFile("http://fastdl.mongodb.org/win32/mongodb-win32-x86_64-2008plus-{{ version }}.zip", "C:\Users\Administrator\Desktop\mongodb.zip")

# Extract zip file to Administrator Desktop
$shell = New-Object -com shell.application
$Desktop = $shell.namespace("C:\Users\Administrator\Desktop")
$ZipFolder = $shell.namespace("C:\Users\Administrator\Desktop\mongodb.zip")
$Desktop.Copyhere($ZipFolder.items())
