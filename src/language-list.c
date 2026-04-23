/*  dvdisaster: Additional error correction for optical media.
 *  Copyright (C) 2004-2017 Carsten Gnoerlich.
 *  Copyright (C) 2019-2021 The dvdisaster development team.
 *
 *  Email: support@dvdisaster.org
 *
 *  This file is part of dvdisaster.
 *
 *  dvdisaster is free software: you can redistribute it and/or modify
 *  it under the terms of the GNU General Public License as published by
 *  the Free Software Foundation, either version 3 of the License, or
 *  (at your option) any later version.
 *
 *  dvdisaster is distributed in the hope that it will be useful,
 *  but WITHOUT ANY WARRANTY; without even the implied warranty of
 *  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *  GNU General Public License for more details.
 *
 *  You should have received a copy of the GNU General Public License
 *  along with dvdisaster. If not, see <http://www.gnu.org/licenses/>.
 */

/*** src type: only GUI code ***/

#ifdef WITH_GUI_YES
#include "dvdisaster.h"

/*
 * Runtime discovery of installed UI translations.
 *
 * We probe for locale/<code>/LC_MESSAGES/dvdisaster.mo in the same three
 * places bindtextdomain() tries in src/dvdisaster.c, in the same order:
 *   1. SRCDIR/locale (if embedded)
 *   2. ./locale (portable ZIP layout -- this is what Windows uses)
 *   3. LOCALEDIR (system install)
 *
 * The first directory that contains at least one .mo wins, and the
 * resulting list is what the preferences dropdown populates from.
 *
 * Codes must match the subdir names under locale/ (which in turn match
 * the entries in PO_LOCALES in GNUmakefile.template). To add a new
 * language: drop a new xx.po in locale/, list it in PO_LOCALES, and add
 * one row to LANG_NAMES below for the human-readable endonym.
 */

static const struct { const char *code; const char *endonym; } LANG_NAMES[] = {
   { "be",    "Беларуская"         },
   { "cs",    "Čeština"            },
   { "de",    "Deutsch"            },
   { "it",    "Italiano"           },
   { "ka",    "ქართული"            },
   { "pl",    "Polski"             },
   { "pt_BR", "Português (Brasil)" },
   { "ru",    "Русский"            },
   { "sv",    "Svenska"            },
   { "tr",    "Türkçe"             },
   { "uk",    "Українська"         },
};

#define N_LANG_NAMES (sizeof(LANG_NAMES) / sizeof(LANG_NAMES[0]))

static int locale_root_has_any(const char *root)
{  if(!root || !*root) return 0;
   for(size_t i = 0; i < N_LANG_NAMES; i++)
   {  char *mo = g_strdup_printf("%s/%s/LC_MESSAGES/dvdisaster.mo",
                                 root, LANG_NAMES[i].code);
      int exists = g_file_test(mo, G_FILE_TEST_EXISTS);
      g_free(mo);
      if(exists) return 1;
   }
   return 0;
}

static char *find_locale_root(void)
{
#ifdef WITH_EMBEDDED_SRC_PATH_YES
   {  char *p = g_strdup_printf("%s/locale", SRCDIR);
      if(locale_root_has_any(p)) return p;
      g_free(p);
   }
#endif
   {  char buf[1024];
      if(getcwd(buf, sizeof(buf)))
      {  char *p = g_strdup_printf("%s/locale", buf);
         if(locale_root_has_any(p)) return p;
         g_free(p);
      }
   }
#ifdef LOCALEDIR
   {  char *p = g_strdup(LOCALEDIR);
      if(locale_root_has_any(p)) return p;
      g_free(p);
   }
#endif
   return NULL;
}

/*
 * Returns a GList of newly-allocated language code strings
 * (e.g. "de", "pt_BR") for which a compiled .mo exists on disk.
 * Caller frees with g_list_free_full(list, g_free).
 */
GList *GuiDiscoverUiLanguages(void)
{  GList *out = NULL;
   char *root = find_locale_root();
   if(!root) return NULL;

   for(size_t i = 0; i < N_LANG_NAMES; i++)
   {  char *mo = g_strdup_printf("%s/%s/LC_MESSAGES/dvdisaster.mo",
                                 root, LANG_NAMES[i].code);
      if(g_file_test(mo, G_FILE_TEST_EXISTS))
         out = g_list_append(out, g_strdup(LANG_NAMES[i].code));
      g_free(mo);
   }
   g_free(root);
   return out;
}

const char *GuiLanguageEndonym(const char *code)
{  if(!code) return "";
   for(size_t i = 0; i < N_LANG_NAMES; i++)
      if(!strcmp(code, LANG_NAMES[i].code))
         return LANG_NAMES[i].endonym;
   return code;
}

#endif /* WITH_GUI_YES */
