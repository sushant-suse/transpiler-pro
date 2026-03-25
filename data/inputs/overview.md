---
description: Manage your Losant Application and it's resources on your local disk.
sidebar_position: 1
sidebar_label: Overview
---

# Losant CLI

Losant CLI is a command line tool to help manage your [Losant Application](/applications/overview/) and its resources. It easily lets you manage [Experience Views](/experiences/views/), [Experience Versions](/experiences/versions/), [Data Tables](/data-tables/overview/), and [Files](/applications/files/) in your Applications.

## Installation

The Losant CLI requires you to download and install Node.js version 14 or higher and NPM. You can use the [Node installer](https://nodejs.org/en/download/) to install both Node and NPM. Once you have those installed, run `npm install -g losant-cli`. To check that you have install Losant CLI properly run `losant --help`, and that will print all of the commands you have available. See our [GitHub repository](https://github.com/Losant/losant-cli) if you are having trouble installing.

## Usage

Here are all the following resources the CLI supports:

- [**Experiences**](/cli/experience/): Manage [Experience Views](/experiences/views/), and [Versions](/experiences/versions/) from the command line.

- [**Files**](/cli/files/): Manage [public Application Files](/applications/files/) from the command line.

- [**Data Tables**](/cli/data-tables/): Manage [Data Tables](/data-tables/overview/) from the command line.

## Setup

Before you get started, there are a couple things you have to configure first. The first will be setting up your user profile for the Losant CLI. This can be done by either by the [login](#login) command or the [set-token](#set-token) command. Either will allow your user to access applications and their resources.

### Login

After installing, one way to set up your user profile is to run the command `losant login`. This will prompt you to enter your Losant account email address. If your user is **not** connected to a Single Sign-On Provider, you will be prompted to enter your password, and optionally your multi-factor authentication code. **If you do not have multi-factor authentication enabled, just hit enter to skip multi-factor authentication.**

![Losant Login](/images/cli/login.png 'Login')

If you account is connected to a Single Sign-On Provider, you will be prompted to enter a [User Token](#creating-a-user-token).

![Losant Login Token](/images/cli/login-token.png 'Login Token')

Once you have successfully authenticated with our API, a file will be created at `~/.losant/.credentials.yml` containing your authentication token. This token will be used across all of your Losant configured directories.

![Losant Success Login](/images/cli/login-success.png 'Login Success')

If authentication fails you will be prompted to re-enter your email, password and multi-factor authentication.

![Losant Retry Login](/images/cli/login-failure.png 'Login Retry')

### Set-Token

![Losant Set-Token](/images/cli/set-token.png 'Set-Token')

The second way to set up your user profile is to run the command `losant set-token [token]`. After installation, running this command will prompt you to enter a [User Token](#creating-a-user-token) or pass in the User Token as the command argument to avoid being prompted. The set-token command is an easy way to give a non-Losant user access to a specific application or all of your applications without having to give them the full credentials to the UI.

#### Creating a User Token

A [User Token](/user-accounts/user-tokens) can be created in the [UI](/user-accounts/user-tokens#generating-an-api-token) or through the [API](/rest-api/user-api-tokens#post). If you are using the UI to create a User Token, select the "CLI developer" permission option. This permission option scopes the exact permissions needed to manage only the resources that can be managed in the CLI. If you are creating a User Token with the API, set the field `scope` to `all.User.cli`.

### Configure

After you have successfully set up your user profile, you are now ready to configure a directory.

Create or go to a directory that you want to keep your Losant Application resources, then run `losant configure`. This will link the current directory to one of your Losant Applications.

![Losant Configure](/images/cli/configure.png 'Configure')

When you run this command, you will be prompted to give a (or part of a) Losant Application name. If multiple Applications come back with similar names we will present you with a list to choose from. If you don't find the application you are looking for, choose `none of these, search again`, and it will re-prompt you for another Application name.

Once you have picked the Losant Application, it will automatically try to download your Application's [Experience Views](/experiences/views/). It will then prompt you to download your [Application's Files](/applications/files/) followed by your [Application's Data Tables](/data-tables/overview/).

![Losant Configure Success](/images/cli/configure-success.png 'Configure Success')

Once you have configured the directory, you will notice a few newly created directories in your configured directory.

#### Losant CLI Directories

- `.losant/`: This is where we store dotfiles with your YAML configuration.
- `dataTables/`: This is where all of your local data tables will be stored as CSV files.
- `experience/components/`: This is where all of your local experience components will be.
- `experience/pages/`: This is where all of your local experience pages will be.
- `experience/layouts/`: This is where all of your local experience layouts will be.
- `files/`: This is where all of your local files will be. The Files directory will match the top-level directory on your Application's [public Files](/applications/files/#public-files). For example, if on Losant you have a public file at `/foo/bar/helloworld.txt`, that file will be downloaded and placed at `files/foo/bar/helloworld.txt`. ([Private files](/applications/files/#private-files) are not supported by the Losant CLI.)
