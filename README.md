# Stockton

You know, Stockton, because it assists the Mailman.


## Let me tell you a tale

So you've bought yourself a super fancy schmancy domain, `super-cool-domain.com` and, to let everyone know how cool you are, you want to change your email address to `joecool@super-cool-domain.com` but you already have an email account at a place like Gmail and you don't really want to give that up, instead you would rather just have your new fancy email address forward to your existing gmail address, well, Stockton is here to help.

Stockton is an email proxy server, its goal is to easily allow you to forward one email address, say `joecool@super-cool-domain.com` to another email account, say `joecool@gmail.com`, transparently, and with as little hassle as possible.


## Setup and installation

Use pip:

    $ sudo pip install stockton

Then, after installation, just run:

    $ stockton install super-cool-domain.com \
    > --proxy-email=joecool@gmail.com \
    > --mailserver=mail.super-cool-domain.com \
    > --smtp_password="..." \
    > --state=CA \
    > --city="San Francisco"

That will setup Stockton and report what dns changes you will need to make to `super-cool-domain.com` in order to get everything working.


### Domain files

Stockton can, most likely, host as many domains as you want to throw at it, and you can configure those domains using configuration files, so let's say you had a file like this:

```
# config file for super-cool-domain.org

# let's send some email to joe, some to his super wonderful wife, and some to both of them
joecool@super-cool-domain.org                     joecool@gmail.com
janecool@super-cool-domain.org                    janecool@gmail.com
family@super-cool-domain.org                      joecool@gmail.com,janecool@gmail.com

# all stray emails should go to Joe
@super-cool-domain.org                            joecool@gmail.com
```

Now you can add your new `super-cool-domain.org` to your mailserver using:

    $ stockton add-domain super-cool-domain.org --proxy-file=/path/to/domain.config

And Stockton will add the domain to your mailserver and let you know what dns changes you need to make to make your new domain work.


Now that all this explaining is done, here's some animated gifs of John Stockton assisting Karl Malone...

![](https://github.com/Jaymon/stockton/blob/master/images/stockton-to-malone-3.gif)

-------------------------------------------------------------------------------

![](https://github.com/Jaymon/stockton/blob/master/images/stockton-to-malone-2.gif)

-------------------------------------------------------------------------------

![](https://github.com/Jaymon/stockton/blob/master/images/stockton-to-malone-1.gif)

