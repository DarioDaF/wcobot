##!/usr/bin/env python
# -*- coding: utf-8 -*-
# pylint: disable=W0613, C0116
# type: ignore[union-attr]
# This program is dedicated to the public domain under the CC0 license.

"""
Simple Bot to send timed Telegram messages.

This Bot uses the Updater class to handle the bot and the JobQueue to send
timed messages.

First, a few handler functions are defined. Then, those functions are passed to
the Dispatcher and registered at their respective places.
Then, the bot is started and runs until we press Ctrl-C on the command line.

Usage:
Basic Alarm Bot example, sends a message after a set time.
Press Ctrl-C on the command line or send a signal to the process to stop the
bot.
"""

VERSION = '0.2.1'

import logging

from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext, Job

from gen.wco import checkPage

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)

logger = logging.getLogger(__name__)


# Define a few command handlers. These usually take the two arguments update and
# context. Error handlers also receive the raised TelegramError object in error.
def start(update: Update, context: CallbackContext) -> None:
    update.message.reply_text(f'Hi (V.{VERSION})! Use /scrape <seconds> <page> to set the target')

MAX_ENTRIES = 5

class UserScrapeCtx:
    def __init__(self):
        self.latests: dict[str, str] = {}
        self.jobs: dict[str, Job] = {}

class ScrapeJobs:
    def __init__(self):
        self.jobs: dict[int, UserScrapeCtx] = {}
    def add(self, context: CallbackContext, chat_id, page, interval):
        job_name = f'Scrape|{chat_id}|{page}'
        if chat_id not in self.jobs:
            self.jobs[chat_id] = UserScrapeCtx()
        job = context.job_queue.run_repeating(alarm, interval, context=(chat_id, page, self.jobs[chat_id].latests), name=job_name)
        self.jobs[chat_id].jobs[page] = job
        return job
    def remove(self, chat_id, page = ''):
        if chat_id not in self.jobs:
            return 0
        user_jobs = self.jobs[chat_id].jobs
        target_jobs = []
        if page != '':
            if page in user_jobs:
                target_jobs.append(user_jobs[page])
                del user_jobs[page]
        else:
            target_jobs.extend(user_jobs.values())
            user_jobs.clear()
        for job in target_jobs:
            job.schedule_removal()
        return len(target_jobs)
scrape_jobs = ScrapeJobs()

def alarm(context: CallbackContext):
    """Send the alarm message."""
    chat_id, page, latests = context.job.context
    resp = ''
    i = 0
    for title, href in checkPage(page, latests):
        if i < MAX_ENTRIES:
            resp += f'{title}\n'
        i += 1
    if i > MAX_ENTRIES:
        resp += f'... [other {i - MAX_ENTRIES} elements]'
    if resp != '':
        context.bot.send_message(chat_id, text=resp)

def set_scrape(update: Update, context: CallbackContext) -> None:
    """Add a job to the queue."""
    chat_id = update.message.chat_id
    try:
        # args[0] should contain the time for the timer in seconds
        interval = int(context.args[0])
        page = context.args[1] # Check page validity
        if interval <= 0:
            update.message.reply_text('Sorry we can not go back to future!')
            return

        job_removed = scrape_jobs.remove(chat_id, page) > 0
        job = scrape_jobs.add(context, chat_id, page, interval)

        text = 'Timer successfully set!'
        if job_removed:
            text += ' Old one was removed.'
        update.message.reply_text(text)

        job.run(context.dispatcher) # Force first run

    except (IndexError, ValueError):
        update.message.reply_text('Usage: /scrape <seconds> <page>')


def unset(update: Update, context: CallbackContext) -> None:
    """Remove the job if the user changed their mind."""
    chat_id = update.message.chat_id
    page = ''
    if len(context.args) > 0:
        page = context.args[0]
    job_removed = scrape_jobs.remove(chat_id, page)
    text = f'Timer successfully cancelled! {job_removed} jobs removed.'
    update.message.reply_text(text)


def main():
    """Run bot."""
    # Create the Updater and pass it your bot's token.
    # Make sure to set use_context=True to use the new context based callbacks
    # Post version 12 this will no longer be necessary
    TOKEN = "x"
    updater = Updater(TOKEN, use_context=True)

    # Get the dispatcher to register handlers
    dispatcher = updater.dispatcher

    # on different commands - answer in Telegram
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("help", start))
    dispatcher.add_handler(CommandHandler("scrape", set_scrape))
    dispatcher.add_handler(CommandHandler("unset", unset))

    # Start the Bot
    updater.start_polling()

    # Block until you press Ctrl-C or the process receives SIGINT, SIGTERM or
    # SIGABRT. This should be used most of the time, since start_polling() is
    # non-blocking and will stop the bot gracefully.
    updater.idle()


if __name__ == '__main__':
    main()
