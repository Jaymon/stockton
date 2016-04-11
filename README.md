# Stockton

You know, Stockton, because it assists the Mailman.


## Let me paint you a word picture

You have an existing email address that you use for everything, say `joecool@gmail.com`, and you like this email address, you really do. But your mom told you it's time to grow up and so you purchased a super fancy schmancy domain, `super-cool-domain.com` with the intent to up your email address game. You just know you'll look so adult with `joecool@super-cool-domain.com` on your business cards.

There's just one flaw in your master plan, it took you so long to get `joecool@gmail.com` setup with the filters the way you like them, and you have 2-factor setup, it would be a shame to start all over fresh, this is where Stockton comes in.

Stockton is an email proxy server, its goal is to easily allow you to forward one email address, say `joecool@super-cool-domain.com` to another email account, say your beloved `joecool@gmail.com`, transparently, and with as little hassle as possible.


## So how do I use it?

Use pip:

    $ sudo pip install stockton

Then, after installation, just run:

    $ sudo stockton install super-cool-domain.com \
    > --proxy-email=joecool@gmail.com \
    > --mailserver=mail.super-cool-domain.com \
    > --smtp_password="..."

That will setup Stockton and report what dns changes you will need to make to `super-cool-domain.com` in order to get everything working correctly. Stockton will automatically setup modern email things like [DKIM](http://www.dkim.org/), [SPF](http://www.openspf.org/), and [SRS](http://www.openspf.org/SRS) so your emails won't get lost in spam folders everwhere.


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

And Stockton will add that domain to your mailserver and let you know what dns changes you need to make to make your new domain work.


## FAQ

### Why did you write this?

Good question, I'm glad you asked, turns out I've been a little liberal with the email addresses during the 13+ years I've owned my own domain, I gave some addresses to my parents, some more to my siblings, even my lovely wife got in on the action, and to top it all off, I've probably given out 300-400 unique email addresses in my various travels around the internets (just because!).

So when the time came to finally, (finally!) update my aging mailserver, I had trouble finding a hosted solution that worked for my particular use case (400+ unique email addresses, going to a few dozen unique email addresses) and Stockton was born.

Stockton is designed for my specific use case, multiple domains, all forwarding to different email addresses, if you have this use case, feel free to give it a spin.


### Why the name Stockton?

I'm a fan of 1990's Utah Jazz references, here are some animated gifs to illustrate Stockton assisting the Mailman...

![](https://github.com/Jaymon/stockton/blob/master/images/stockton-to-malone-3.gif)

![](https://github.com/Jaymon/stockton/blob/master/images/stockton-to-malone-2.gif)

![](https://github.com/Jaymon/stockton/blob/master/images/stockton-to-malone-1.gif)

