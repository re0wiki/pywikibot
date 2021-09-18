#!/usr/bin/python
r"""
This is a Bot to add text to the top or bottom of a page.

By default this adds the text to the bottom above the categories and interwiki.

These command line parameters can be used to specify which pages to work on:

&params;

Furthermore, the following command line parameters are supported:

-text             Define what text to add. "\n" are interpreted as newlines.

-textfile         Define a texfile name which contains the text to add

-summary          Define the summary to use

-up               If used, put the text at the top of the page

-always           If used, the bot won't ask if it should add the specified
                  text

-major            If used, the edit will be saved without the "minor edit" flag

-talkpage         Put the text onto the talk page instead
-talk

-excepturl        Use the html page as text where you want to see if there's
                  the text, not the wiki-page.

-noreorder        Avoid reordering cats and interwiki

Example
-------

1. Append 'hello world' to the bottom of the sandbox:

    python pwb.py add_text -page:Wikipedia:Sandbox \
        -summary:"Bot: pywikibot practice" -text:"hello world"

2. Add a template to the top of the pages with 'category:catname':

    python pwb.py add_text -cat:catname -summary:"Bot: Adding a template" \
        -text:"{{Something}}" -except:"\{\{([Tt]emplate:|)[Ss]omething" -up

3. Command used on it.wikipedia to put the template in the page without any
   category:

    python pwb.py add_text -except:"\{\{([Tt]emplate:|)[Cc]ategorizzare" \
        -text:"{{Categorizzare}}" -excepturl:"class='catlinks'>" -uncat \
        -summary:"Bot: Aggiungo template Categorizzare"
"""
#
# (C) Pywikibot team, 2007-2021
#
# Distributed under the terms of the MIT license.
#
import codecs
import re
import sys
from typing import Optional, Union

import pywikibot

from pywikibot import config, i18n, pagegenerators, textlib
from pywikibot.backports import Dict, Tuple
from pywikibot.bot import (
    AutomaticTWSummaryBot,
    ExistingPageBot,
    NoRedirectPageBot,
)
from pywikibot.bot_choice import QuitKeyboardInterrupt
from pywikibot.exceptions import (
    EditConflictError,
    IsRedirectPageError,
    LockedPageError,
    NoPageError,
    PageSaveRelatedError,
    ServerError,
    SpamblacklistError,
)
from pywikibot.tools import deprecated
from pywikibot.tools.formatter import color_format

DEFAULT_ARGS = {
    'text': '',
    'textfile': '',
    'summary': '',
    'up': False,
    'always': False,
    'minor': True,
    'talk_page': False,
    'reorder': True,
    'regex_skip_url': '',
}

ARG_PROMPT = {
    '-text': 'What text do you want to add?',
    '-textfile': 'Which text file do you want to append to the page?',
    '-summary': 'What summary do you want to use?',
    '-excepturl': 'What url pattern should we skip?',
}


docuReplacements = {'&params;': pagegenerators.parameterHelp}  # noqa: N816


@deprecated('Page.text, NoRedirectPageBot class and BaseBot.skip_page() '
            '(see add_text.AddTextBot for example)', since='6.4.0')
def get_text(page: pywikibot.page.BasePage, old: Optional[str],
             create: bool) -> str:
    """
    Get text on page. If old is not None, return old.

    :param page: The page to get text from
    :param old: If not None, return this rather than the page's text
    :param create: Declare that the page will be created if it doesn't exist
    :return: The page's text or the old parameter if not None
    """
    if old is not None:
        return old

    try:
        return page.get()
    except NoPageError:
        if create:
            pywikibot.output("{} doesn't exist, creating it!"
                             .format(page.title()))
            return ''
        else:
            pywikibot.output("{} doesn't exist, skip!".format(page.title()))
            return None
    except IsRedirectPageError:
        pywikibot.output('{} is a redirect, skip!'.format(page.title()))
        return None


@deprecated('BaseBot.userPut()', since='6.4.0')
def put_text(page: pywikibot.page.BasePage, new: str, summary: str, count: int,
             asynchronous: bool = False) -> Optional[bool]:
    """
    Save the new text.

    :param page: The page to change the text of
    :param new: The new text for the page
    :param summary: Summary of the page change
    :param count: Maximum number of attempts to reach the server
    :param asynchronous: If True, saves the page asynchronously
    :return: True if successful, False if unsuccessful, and None if
        awaiting the server
    """
    page.text = new
    try:
        page.save(summary=summary, asynchronous=asynchronous,
                  minor=page.namespace() != 3)
    except EditConflictError:
        pywikibot.output('Edit conflict! skip!')
    except ServerError:
        if count <= config.max_retries:
            pywikibot.output('Server Error! Wait..')
            pywikibot.sleep(config.retry_wait)
            return None
        raise ServerError(
            'Server Error! Maximum retries exceeded')
    except SpamblacklistError as e:
        pywikibot.output(
            'Cannot change {} because of blacklist entry {}'
            .format(page.title(), e.url))
    except LockedPageError:
        pywikibot.output('Skipping {} (locked page)'.format(page.title()))
    except PageSaveRelatedError as error:
        pywikibot.output('Error putting page: {}'.format(error.args))
    else:
        return True
    return False


@deprecated('Page.text, textlib.add_text, NoRedirectPageBot class, '
            'BaseBot.skip_page() and CurrentPage.put_current() '
            '(see add_text.AddTextBot for example)', since='6.4.0')
def add_text(page: pywikibot.page.BasePage, addText: str,
             summary: Optional[str] = None,
             regexSkip: Optional[str] = None,
             regexSkipUrl: Optional[str] = None,
             always: bool = False, up: bool = False,
             putText: bool = True, oldTextGiven: Optional[str] = None,
             reorderEnabled: bool = True, create: bool = False
             ) -> Union[Tuple[bool, bool, bool], Tuple[str, str, bool]]:
    """
    Add text to a page.

    :param page: The page to add text to
    :param addText: Text to add
    :param summary: Change summary, if None this uses the beginning of addText
    :param regexSkip: Abort if the text on the page matches this
    :param regexSkipUrl: Abort if the url matches this
    :param always: Edit without user confirmation
    :param up: Append text to the top of the page if True, otherwise the
        bottom
    :param putText: Save changes to the page if True, otherwise return
        (text, newtext, always)
    :param oldTextGiven: If None fetch page text, else use this text
    :param reorderEnabled: If True place text above categories and
        interwiki, else place at page bottom. No effect if up = False.
    :param create: Create the page if it does not exist
    :return: (success, success, always) if putText is True, otherwise
        (text, newtext, always)
    """
    site = page.site
    if not summary:
        summary = i18n.twtranslate(site, 'add_text-adding',
                                   {'adding': addText[:200]})
    if putText:
        pywikibot.output('Loading {}...'.format(page.title()))

    text = get_text(page, oldTextGiven, create)
    if text is None:
        return (False, False, always)

    # Understand if the bot has to skip the page or not
    # In this way you can use both -except and -excepturl
    if regexSkipUrl is not None:
        url = page.full_url()
        result = re.findall(regexSkipUrl, site.getUrl(url))
        if result != []:
            pywikibot.output(
                'Exception! regex (or word) used with -exceptUrl '
                'is in the page. Skip!\n'
                'Match was: {}'.format(result))
            return (False, False, always)
    if regexSkip is not None:
        result = re.findall(regexSkip, text)
        if result != []:
            pywikibot.output(
                'Exception! regex (or word) used with -except '
                'is in the page. Skip!\n'
                'Match was: {}'.format(result))
            return (False, False, always)
    # If not up, text put below
    if not up:
        newtext = text
        # Translating the \\n into binary \n
        addText = addText.replace('\\n', '\n')
        if reorderEnabled:
            # Getting the categories
            categoriesInside = textlib.getCategoryLinks(newtext, site)
            # Deleting the categories
            newtext = textlib.removeCategoryLinks(newtext, site)
            # Getting the interwiki
            interwikiInside = textlib.getLanguageLinks(newtext, site)
            # Removing the interwiki
            newtext = textlib.removeLanguageLinks(newtext, site)

            # Adding the text
            newtext += '\n' + addText
            # Reputting the categories
            newtext = textlib.replaceCategoryLinks(newtext,
                                                   categoriesInside, site,
                                                   True)
            # Adding the interwiki
            newtext = textlib.replaceLanguageLinks(newtext, interwikiInside,
                                                   site)
        else:
            newtext += '\n' + addText
    else:
        newtext = addText + '\n' + text

    if not putText:
        # If someone load it as module, maybe it's not so useful to put the
        # text in the page
        return (text, newtext, always)

    if text != newtext:
        pywikibot.output(color_format(
            '\n\n>>> {lightpurple}{0}{default} <<<', page.title()))
        pywikibot.showDiff(text, newtext)

    # Let's put the changes.
    error_count = 0
    while True:
        if not always:
            try:
                choice = pywikibot.input_choice(
                    'Do you want to accept these changes?',
                    [('Yes', 'y'), ('No', 'n'), ('All', 'a'),
                     ('open in Browser', 'b')], 'n')
            except QuitKeyboardInterrupt:
                sys.exit('User quit bot run.')

            if choice == 'a':
                always = True
            elif choice == 'n':
                return (False, False, always)
            elif choice == 'b':
                pywikibot.bot.open_webbrowser(page)
                continue

        # either always or choice == 'y' is selected
        result = put_text(page, newtext, summary, error_count,
                          asynchronous=not always)
        if result is not None:
            return (result, result, always)
        error_count += 1


class AddTextBot(AutomaticTWSummaryBot, ExistingPageBot, NoRedirectPageBot):

    """A bot which adds a text to a page."""

    summary_key = 'add_text-adding'
    update_options = DEFAULT_ARGS

    @property
    def summary_parameters(self):
        """Return a dictionary of all parameters for i18n.

        Line breaks are replaced by dash.
        """
        text = re.sub(r'\r?\n', ' - ', self.opt.text[:200])
        return {'adding': text}

    def setup(self):
        """Read text to be added from file."""
        if self.opt.textfile:
            with codecs.open(self.opt.textfile, 'r',
                             config.textfile_encoding) as f:
                self.opt.text = f.read()
        else:
            # Translating the \\n into binary \n if given from command line
            self.opt.text = self.opt.text.replace('\\n', '\n')

        if self.opt.talk_page:
            self.generator = pagegenerators.PageWithTalkPageGenerator(
                self.generator, return_talk_only=True)

    def skip_page(self, page):
        """Skip if -exceptUrl matches or page does not exists."""
        if page.exists() and self.opt.regex_skip_url:
            url = page.full_url()
            result = re.findall(self.opt.regex_skip_url, page.site.getUrl(url))

            if result:
                pywikibot.warning(
                    'Skipping {page} because -excepturl matches {result}.'
                    .format(page=page, result=result))
                return True

        if page.isTalkPage() and not page.exists():
            pywikibot.output("{} doesn't exist, creating it!".format(page))
            return False

        return super().skip_page(page)

    def treat_page(self):
        """Add text to the page."""
        text = self.current_page.text

        if self.opt.up:
            text = self.opt.text + '\n' + text
        elif not self.opt.reorder:
            text += '\n' + self.opt.text
        else:
            text = textlib.add_text(text, self.opt.text,
                                    site=self.current_page.site)

        self.put_current(text, summary=self.opt.summary, minor=self.opt.minor)


def main(*argv: str) -> None:
    """
    Process command line arguments and invoke bot.

    If args is an empty list, sys.argv is used.

    :param argv: Command line arguments
    """
    generator_factory = pagegenerators.GeneratorFactory()

    try:
        options = parse(argv, generator_factory)
    except ValueError as exc:
        pywikibot.bot.suggest_help(additional_text=str(exc))
        return

    generator = generator_factory.getCombinedGenerator()
    if pywikibot.bot.suggest_help(missing_generator=not generator):
        return

    bot = AddTextBot(generator=generator, **options)
    bot.run()


def parse(argv: Tuple[str, ...],
          generator_factory: pagegenerators.GeneratorFactory
          ) -> Dict[str, str]:
    """
    Parses our arguments and provide a named tuple with their values.

    :param argv: input arguments to be parsed
    :param generator_factory: factory that will determine the page to edit
    :return: dictionary with our parsed arguments
    :raise ValueError: invalid arguments received
    """
    args = dict(DEFAULT_ARGS)
    argv = pywikibot.handle_args(argv)
    argv = generator_factory.handle_args(argv)

    for arg in argv:
        option, _, value = arg.partition(':')

        if not value and option in ARG_PROMPT:
            value = pywikibot.input(ARG_PROMPT[option])

        if option in ('-text', '-textfile', '-summary'):
            args[option[1:]] = value
        elif option in ('-up', '-always'):
            args[option[1:]] = True
        elif option in ('-talk', '-talkpage'):
            args['talk_page'] = True
        elif option == '-noreorder':
            args['reorder'] = False
        elif option == '-excepturl':
            args['regex_skip_url'] = value
        elif option == '-major':
            args['minor'] = False
        else:
            raise ValueError("Argument '{}' is unrecognized".format(option))

    if not args['text'] and not args['textfile']:
        raise ValueError("Either the '-text' or '-textfile' is required")

    if args['text'] and args['textfile']:
        raise ValueError("'-text' and '-textfile' cannot both be used")

    return args


if __name__ == '__main__':
    main()
