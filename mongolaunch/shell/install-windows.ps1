<powershell>
# Download MongoDB
$webClient = New-Object System.Net.WebClient
$webClient.DownloadFile("http://fastdl.mongodb.org/win32/mongodb-win32-x86_64-2008plus-{{ version }}.zip", "C:\Users\Administrator\Desktop\mongodb.zip")

# Extract zip file to Administrator Desktop
$shell = New-Object -com shell.application
$Desktop = $shell.namespace("C:\Users\Administrator\Desktop")
$ZipFolder = $shell.namespace("C:\Users\Administrator\Desktop\mongodb.zip")
$Desktop.Copyhere($ZipFolder.items())

# Create dbpath = c:\data\db
# You may need to change this if you provide a different --dbpath in your config file
md C:\data\db
# Logpath
md C:\logs

# Firewall rules allowing mongod, mongos, and the mongo shell
netsh advfirewall firewall add rule name="Allowing mongod" dir=in action=allow program="C:\Users\Administrator\Desktop\mongodb-win32-x86_64-2008plus-{{ version }}\bin\mongod.exe"
netsh advfirewall firewall add rule name="Allowing mongos" dir=in action=allow program="C:\Users\Administrator\Desktop\mongodb-win32-x86_64-2008plus-{{ version }}\bin\mongos.exe"
netsh advfirewall firewall add rule name="Allowing mongo shell" dir=in action=allow program="C:\Users\Administrator\Desktop\mongodb-win32-x86_64-2008plus-{{ version }}\bin\mongo.exe"

# Add mongo executable as a service + start it
if ("{{ bin }}" -eq "mongos") {
  C:\Users\Administrator\Desktop\mongodb-win32-x86_64-2008plus-{{ version }}\bin\{{ bin }} --configdb {{ configdb }} --logpath C:\logs\mongos.log {{ options }} --install
  net start MongoS
} else {
  C:\Users\Administrator\Desktop\mongodb-win32-x86_64-2008plus-{{ version }}\bin\{{ bin }} --logpath C:\logs\mongod.log {{ options }} --install
  net start MongoDB
}
</powershell>
