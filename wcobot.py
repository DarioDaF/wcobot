##!/usr/bin/env python
# -*- coding: utf-8 -*-
# pylint: disable=W0613, C0116
# type: ignore[union-attr]
# This program is dedicated to the public domain under the CC0 license.

"""
Bot to check for updates on sites periodically and send messages when new
stuff is present.

Bot based on Updater class to handle JobQueues to send timed messages.

Usage:
Press Ctrl-C on the command line or send a signal to the process to stop the bot.
"""

VERSION = '0.3.1'
SAVE_FILE = './wcobot.json'
TOKEN_FILE = './wcobot.token'
MAX_ENTRIES = 5

import logging, json, os

from telegram import Update, ParseMode
from telegram.ext import Updater, CommandHandler, CallbackContext, Job, JobQueue
#from telegram.utils.helpers import escape_markdown
from html import escape

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

class JobDescr:
    def __init__(self, chat_id, page: str, interval: int, latest: str = ''):
        self.chat_id = chat_id
        self.page = page
        self.interval = interval
        self.job: Job = None
        self.latest = latest
    def create(self, job_queue: JobQueue):
        job_name = f'Scrape|{self.chat_id}|{self.page}'
        self.job = job_queue.run_repeating(_alarm, interval=self.interval, context=self, name=job_name)
        return self.job
    def remove(self):
        if self.job != None:
            self.job.schedule_removal()
            self.job = None
    def is_valid(self):
        return self.job != None
    def to_dict(self):
        return {
            'chat_id': self.chat_id,
            'page': self.page,
            'interval': self.interval,
            'latest': self.latest,
        }

class ScrapeJobs:
    def __init__(self):
        self.jobs: dict[int, dict[str, JobDescr]] = {}
    def add(self, job_queue: JobQueue, chat_id, page, interval, latest=''):
        if chat_id not in self.jobs:
            self.jobs[chat_id] = {}
        if page in self.jobs[chat_id]:
            self.jobs[chat_id][page].remove()
            #del self.jobs[chat_id][page] # Gets overwritten
        jd = JobDescr(chat_id, page, interval, latest)
        self.jobs[chat_id][page] = jd
        jd.create(job_queue)
        return jd
    def remove(self, chat_id, page = ''):
        if chat_id not in self.jobs:
            return 0
        user_jobs = self.jobs[chat_id]
        target_jobs: list[JobDescr] = []
        if page != '':
            if page in user_jobs:
                target_jobs.append(user_jobs[page])
                del user_jobs[page]
        else:
            target_jobs.extend(user_jobs.values())
            user_jobs.clear()
        for job in target_jobs:
            job.remove()
        return len(target_jobs)
scrape_jobs = ScrapeJobs()

def _alarm(context: CallbackContext):
    """Send the alarm message."""
    job_descr: JobDescr = context.job.context
    resp = ''
    i = 0

    latest_list = { job_descr.page: job_descr.latest }
    for title, href in checkPage(job_descr.page, latest_list):
        if i < MAX_ENTRIES:
            resp += f'<a href="{escape(href)}">{escape(title)}</a>\n'
        i += 1
    job_descr.latest = latest_list[job_descr.page]

    if i > MAX_ENTRIES:
        resp += f'<i>... [other {i - MAX_ENTRIES} elements]</i>'
    if resp != '':
        context.bot.send_message(job_descr.chat_id, text=resp, parse_mode=ParseMode.HTML)

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
        jd = scrape_jobs.add(context.job_queue, chat_id, page, interval)

        text = 'Timer successfully set!'
        if job_removed:
            text += ' Old one was removed.'
        update.message.reply_text(text)

        jd.job.run(context.dispatcher) # Force first run

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
    with open(TOKEN_FILE, 'r') as fp:
        TOKEN = fp.read().strip()
    updater = Updater(TOKEN, use_context=True)

    # Get the dispatcher to register handlers
    dispatcher = updater.dispatcher

    # on different commands - answer in Telegram
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("help", start))
    dispatcher.add_handler(CommandHandler("scrape", set_scrape))
    dispatcher.add_handler(CommandHandler("unset", unset))

    # Load Jobs
    if os.path.isfile(SAVE_FILE):
        logger.info('Loading saved jobs')
        with open(SAVE_FILE, 'r') as fp:
            all_jobs_data = json.load(fp)
        for job in all_jobs_data:
            scrape_jobs.add(updater.job_queue, job['chat_id'], job['page'], job['interval'], job['latest'])

    # Start the Bot
    updater.start_polling()

    # Block until you press Ctrl-C or the process receives SIGINT, SIGTERM or
    # SIGABRT. This should be used most of the time, since start_polling() is
    # non-blocking and will stop the bot gracefully.
    updater.idle()

    # Save jobs
    logger.info('Saving jobs')
    all_jobs_data = []
    for user_jobs in scrape_jobs.jobs.values():
        for job in user_jobs.values():
            all_jobs_data.append(job.to_dict())
    with open(SAVE_FILE, 'w') as fp:
        json.dump(all_jobs_data, fp)

if __name__ == '__main__':
    main()
