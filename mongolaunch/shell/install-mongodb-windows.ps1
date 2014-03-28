# Download MongoDB
$webClient = New-Object System.Net.WebClient
if (! (Test-Path -Path C:\Users\Administrator\Desktop\mongodb-{{ version }}.zip)) {
        $webClient.DownloadFile(
            "http://fastdl.mongodb.org/win32/mongodb-win32-x86_64-2008plus-{{ version }}.zip",
            "C:\Users\Administrator\Desktop\mongodb-{{ version }}.zip"
        )

        # Extract zip file to Administrator Desktop
        $shell = New-Object -com shell.application
        $Desktop = $shell.namespace("C:\Users\Administrator\Desktop")
        $ZipFolder = $shell.namespace("C:\Users\Administrator\Desktop\mongodb-{{ version }}.zip")
        $Desktop.Copyhere($ZipFolder.items())
}

# Dbpath
md -force {{ dbpath }}
# Logpath
$logdir = (Split-Path -Path {{ logpath }})
md -force $logdir

# Firewall rules allowing mongod, mongos, and the mongo shell
netsh advfirewall firewall add rule name="Allowing mongod" dir=in action=allow program="C:\Users\Administrator\Desktop\mongodb-win32-x86_64-2008plus-{{ version }}\bin\mongod.exe"
netsh advfirewall firewall add rule name="Allowing mongos" dir=in action=allow program="C:\Users\Administrator\Desktop\mongodb-win32-x86_64-2008plus-{{ version }}\bin\mongos.exe"
netsh advfirewall firewall add rule name="Allowing mongo shell" dir=in action=allow program="C:\Users\Administrator\Desktop\mongodb-win32-x86_64-2008plus-{{ version }}\bin\mongo.exe"

# Add mongo executable as a service + start it
if ("{{ bin }}" -eq "mongos") {
    C:\Users\Administrator\Desktop\mongodb-win32-x86_64-2008plus-{{ version }}\bin\{{ bin }} --configdb {{ configdb }} --logpath {{ logpath }} {{ options }} --serviceName {{ _id }} --serviceDisplayName {{ _id }} --install
} else {
    C:\Users\Administrator\Desktop\mongodb-win32-x86_64-2008plus-{{ version }}\bin\{{ bin }} --logpath {{ logpath }} --dbpath {{ dbpath }} {{ options }} --serviceName {{ _id }} --serviceDisplayName {{ _id }} --install
}
net start {{ _id }}
