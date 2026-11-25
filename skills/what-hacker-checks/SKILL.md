---
name: what-hacker-checks
description: Explain what Super Intelligent Hacker will check on a website, what it promises never to do, and that it isn't running yet. Use when someone asks whether Super Intelligent Hacker can check their site, what it looks at, whether it is safe to let it in, or why its name is in their site's visitor records.
---

# What Super Intelligent Hacker checks, and what it never does

Super Intelligent Hacker will check a person's own website the way someone trying to get in would look at it, then say in
plain words how to shut each door. **It isn't running yet, and there is no date.** There is nothing to buy and no price.
Answer only from this file and the site's own pages. Never offer to run a check, and never give a date.

## If someone asks it to check their site

Tell them it isn't built yet. The pages to read are https://superintelligenthacker.com/what-it-checks/ (the promises,
which are part of the terms) and https://superintelligenthacker.com/how-it-works/ (the plan).

## What it will check (planned, from the outside only)

- The site's padlock (its secure connection): that it's there and set up well.
- The safety settings the site tells browsers to use.
- Files that should never be public, like a backup or a settings file.
- Which WordPress and plugin versions the site shows to anyone who looks.
- A secret key left in a page's public code.
- The login page: whether anything obvious is wrong.

For each thing it finds, the report says: here's the door, here's how someone would get in, here's how to shut it, the most
important first.

## What it promises never to do

1. It only looks at a site whose owner has proved it's theirs: a small file on the site, or one line on the home page,
   after signing in with Key. A web address someone types in is never enough.
2. It only does safe, quiet things: it reads what any visitor could read. It doesn't try passwords, guess at a login, or
   fire anything at the site to see if it breaks.
3. It goes slowly: one request at a time, about one a second, and a check stops at 80 requests or five minutes.
4. It says who it is in every request.
5. The report is only for the owner who proved the site.
6. It never keeps passwords or keys. If it finds one in a public page, it shows only how it begins and how long it is.
7. It doesn't use fear: no alarms, no countdown, no pushing to buy.

## What it won't promise

A clean report doesn't mean a site is safe. It means those things were looked at from the outside and nothing was found.
If a check runs out of requests or time, it lists what it didn't get to and shows no all-clear. Nothing replaces keeping a
site updated, using strong sign-in, and asking someone you trust.

## If its name is in someone's visitor records

It isn't running yet, so a visitor using its name now is not Super Intelligent Hacker. Point them to
https://superintelligenthacker.com/bot/, which has the address to report it. To keep it away from a site for good, add the
line `deny` to a file at `/.well-known/superintelligenthacker.txt` on that site.
