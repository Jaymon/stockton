# Adding a receive only domain

If you already have a working Stockton installation, you can add a new receiving domain by following these steps


## 1. Create a proxy domain config file

A proxy config file for `example.com` would look something like:

```
joe@example.com							joe@gmail.com
jane@example.com							jane@gmail.com
both@example.com							joe@gmail.com, jane@gmail.com

# catch-all
@example.com								joe@gmail.com
```

Save that file as `example.com.txt`


## 2. Have Stockton update postfix

Run this command as root:

    $ stockton add-domain example.com --proxy-file=/full/path/to/example.com.txt

The output at the end of that command should tell you what DNS records you need to add to `example.com` to make sure your email is functioning correctly. 

Setting DNS is different for every host, so you're on your own here, Stockton should give you all the information you need to correctly add the records.


## 3. Verify DNS is correctly set

After you add the missing DNS records, you can test them by running:

    $ stockton check-domain example.com
    
If it reports all records were found then you're good, you should be able to receive email from the domain now.

