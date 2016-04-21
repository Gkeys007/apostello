#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# apostello documentation build configuration file, created by
# sphinx-quickstart on Tue Oct  6 14:53:59 2015.
#
# This file is execfile()d with the current directory set to its
# containing dir.
#
# Note that not all possible configuration values are present in this
# autogenerated file.
#
# All configuration values have a default; values that are commented out
# serve to show the default.

import inspect
import sys
import os

from django.utils.html import strip_tags

sys.path.insert(0, os.path.abspath('..'))
os.environ['ELVANTO_KEY'] = 'docs'
os.environ['TWILIO_AUTH_TOKEN'] = 'docs'
os.environ['TWILIO_ACCOUNT_SID'] = 'docs'
os.environ['TWILIO_FROM_NUM'] = 'docs'
os.environ['COUNTRY_CODE'] = '44'
os.environ['DJANGO_SETTINGS_MODULE'] = 'settings.test'
import django
django.setup()

import apostello

# -- General configuration ------------------------------------------------
# needs_sphinx = '1.0'
extensions = ['sphinx.ext.autodoc', ]
templates_path = ['_templates']
source_suffix = '.rst'
# source_encoding = 'utf-8-sig'
master_doc = 'index'

# General information about the project.
project = 'apostello'
copyright = '2015, Dean Montgomery'
author = 'Dean Montgomery'

version = '1.6'
# The full version, including alpha/beta/rc tags.
release = '0.1'
language = None
exclude_patterns = ['_build']
# default_role = None
# add_function_parentheses = True
# add_module_names = True
# show_authors = False
pygments_style = 'sphinx'
# modindex_common_prefix = []
# keep_warnings = False
todo_include_todos = False

# -- Options for HTML output ----------------------------------------------

html_theme = 'sphinx_rtd_theme'
# html_theme_options = {}
# html_theme_path = []
# html_title = None
# html_short_title = None
html_logo = '../apostello/static/images/favicons/android-chrome-48x48.png'
html_favicon = '../apostello/static/images/favicons/favicon.ico'
html_static_path = ['_static']
# html_extra_path = []
# html_last_updated_fmt = '%b %d, %Y'
# html_use_smartypants = True
# html_sidebars = {}
# html_additional_pages = {}
# html_domain_indices = True
# html_use_index = True
# html_split_index = False
# html_show_sourcelink = True
# html_show_sphinx = True
# html_show_copyright = True
# html_use_opensearch = ''
# html_file_suffix = None
# html_search_language = 'en'
# html_search_options = {'type': 'default'}
# html_search_scorer = 'scorer.js'
htmlhelp_basename = 'apostellodoc'

# -- Options for LaTeX output ---------------------------------------------

latex_elements = {
    'papersize': 'a4paper',
    'pointsize': '10pt',
    'preamble': '',
    'figure_align': 'htbp',
}
latex_documents = [
    (
        master_doc, 'apostello.tex', 'apostello Documentation',
        'Dean Montgomery', 'manual'
    ),
]
# latex_logo = None
# latex_use_parts = False
# latex_show_pagerefs = False
# latex_show_urls = False
# latex_appendices = []
# latex_domain_indices = True

# -- Options for manual page output ---------------------------------------

man_pages = [(master_doc, 'apostello', 'apostello Documentation', [author], 1)]
# man_show_urls = False

# -- Options for Texinfo output -------------------------------------------

texinfo_documents = [
    (
        master_doc, 'apostello', 'apostello Documentation', author,
        'apostello', 'One line description of project.', 'Miscellaneous'
    ),
]

# texinfo_appendices = []
# texinfo_domain_indices = True
# texinfo_show_urls = 'footnote'
# texinfo_no_detailmenu = False


def process_docstring(app, what, name, obj, options, lines):
    # https://djangosnippets.org/snippets/2533/
    # This causes import errors if left outside the function
    from django.db import models

    # Only look at objects that inherit from Django's base model class
    if inspect.isclass(obj) and issubclass(obj, models.Model):
        # Grab the field list from the meta class
        fields = obj._meta.fields

        for field in fields:
            if field.name is 'id':
                continue
            # Decode and strip any html out of the field's help text
            help_text = strip_tags(field.help_text)

            # Decode and capitalize the verbose name, for use if there isn't
            # any help text
            verbose_name = field.verbose_name.capitalize()

            if help_text:
                # Add the model field to the end of the docstring as a param
                # using the help text as the description
                lines.append(u':param %s: %s' % (field.attname, help_text))
            else:
                # Add the model field to the end of the docstring as a param
                # using the verbose name as the description
                lines.append(u':param %s: %s' % (field.attname, verbose_name))

            # Add the field's type to the docstring
            lines.append(
                u':type %s: %s' % (field.attname, type(field).__name__)
            )

    # Return the extended docstring
    return lines


def setup(app):
    # Register the docstring processor with sphinx
    app.connect('autodoc-process-docstring', process_docstring)
