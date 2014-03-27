# Dbpath
md {{ dbpath }}
# Logpath
$logdir = (Split-Path -Path {{ logpath }})
md $logdir

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
