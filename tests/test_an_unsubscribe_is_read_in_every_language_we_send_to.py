#!/usr/bin/env python3
"""ISSUE-024, recurring on the path that now carries the whole opt-out.

## The precedent, and why this is the same defect

**ISSUE-024, "the channel-exclusion list was English-only in a Croatian
workspace", CLOSED 2026-09-22.** A safety list written in one language, in an
estate that works in twenty, with a hole in it exactly where the local team
files the invoices. It read `#računi` straight past.

On 2026-09-24 `replies.UNSUBSCRIBE_PATTERNS` held fourteen entries and every
one of them was English - measured, not asserted - while the estate's sourced
pool spans twenty countries and its inbox has received replies from `.de`,
`.pl`, `.cz`, `.fi`, `.nl`, `.se`, `.no`, `.dk`, `.fr`, `.it`, `.si`, `.lt`,
`.ee`, `.lv`, `.hu`, `.hr`, `.gr` and `.rs`. The operator then removed the
unsubscribe link from every campaign, which made the classifier the only thing
between a person asking to be left alone and us continuing to mail them.

## PROVENANCE IS RECORDED PER PHRASE, BECAUSE IT IS NOT UNIFORM

The brief said: a test on REAL phrasings, not invented ones. Here is exactly
how real each one is, and the honest answer is that it varies by language:

    OBSERVED    taken verbatim from this estate's own inbound corpus,
                `work/reply-drafts.jsonl` - the bodies EmailBison delivered
                on 2026-09-22/23. ENGLISH ONLY. There is no corpus of
                non-English opt-out REPLIES on this machine: the TASK-058
                HeyReach cache that held one is gone (both temp directories
                are empty), `work/learning-replies.jsonl` is 179,715 rows of
                metadata with no text at all, and no provider credential is
                available to this session to fetch more.
    REPLY       a person-written reply found in a public mailing-list
                archive - somebody asking a real list to stop mailing them.
    LABEL       the exact words on a real unsubscribe link or button in that
                language, mostly Gmail's own localisation, which is what a
                recipient has in front of them and often pastes back.
    REGULATOR   a data-protection or consumer authority's own wording:
                CNIL, IMY, ICO, UODO, ÚOOÚ, AZOP, DVI, AKI, tietosuoja,
                Datatilsynet, Forbrugerombudsmanden, dataprotection.gov.sk.
    TEMPLATE    a GDPR Article 21 objection or Article 17 erasure letter
                published for people to copy-paste, which they do.

Every phrase here carries its tag, and the merge request's appendix lists the
sources PER LANGUAGE - enough to re-derive any phrase, and deliberately not
claimed as a URL per phrase, which it is not.
**Where a phrasing could not be attested it was NOT added** - not to the
classifier and not to this file. `replies.LANGUAGE_COVERAGE` names the four
languages that are PARTIAL for that reason, and the two scripts that are not
covered at all.

## THE OTHER HALF, AND IT IS THE HALF THAT COSTS MONEY

`OrdinarySentencesAreNotOptOuts` is not a formality. An unsubscribe now
suppresses permanently and agency-wide, so a false positive makes a live
prospect unreachable by every client this agency has, for good. Every sentence
in that corpus is a real ordinary use of a word that sits in the opt-out
vocabulary of its own language - `abmelden` is how German says "log out",
`afmelden` is how Dutch declines a meeting, `baja` is sick leave in a Spanish
out-of-office, `sair` is "to leave" in Portuguese, `odjava` is a Croatian
hotel check-out, `stop` is a metal alloy in Polish. If any of them classifies
as an unsubscribe, the pattern that did it is too wide.
"""
import json
import os
import unittest

from src import replies

#: Provenance tags. See the module docstring.
OBSERVED, REPLY, LABEL, REGULATOR, TEMPLATE = (
    "observed", "reply", "label", "regulator", "template")

#: (language, phrase, provenance). Sources are in the merge request.
OPT_OUTS = (
    # --------------------------------------------------------------- English
    ("en", "no. stop.", OBSERVED),          # EmailBison 1609395, 2026-09-22
    ("en", "stop", OBSERVED),
    ("en", "unsubscribe", LABEL),
    ("en", "Please take me off your mailing list.", REPLY),
    ("en", "Please remove me from your database.", REPLY),
    ("en", "cease and desist", TEMPLATE),
    ("en", "delete my name, address, and any information about me "
           "from your files", TEMPLATE),
    ("en", "I wish to exercise my right of erasure under data protection "
           "law", REGULATOR),
    ("en", "I am hereby objecting to the processing of personal data "
           "concerning me for direct marketing purposes", TEMPLATE),
    ("en", "I am hereby withdrawing said consent", TEMPLATE),
    ("en", "Please no more messages", REPLY),
    ("en", "Cancel subscription", LABEL),
    ("en", "Under the GDPR I ask you to delete my data.", TEMPLATE),
    # ---------------------------------------------------------------- German
    ("de", "Abbestellen", LABEL),
    ("de", "Newsletter abbestellen", LABEL),
    ("de", "Abmelden", LABEL),
    ("de", "Bitte abmelden", REPLY),
    ("de", "Bitte nehmen Sie mich aus Ihrem Verteiler!", REPLY),
    ("de", "Adresse bitte aus dem Verteiler streichen", REPLY),
    ("de", "ich lege hiermit Widerspruch gegen die Verarbeitung meiner "
           "personenbezogenen Daten für Direktwerbung ein", TEMPLATE),
    ("de", "Sollte ich eine Einwilligung erteilt haben, widerrufe ich "
           "diese hiermit.", TEMPLATE),
    ("de", "Bitte keine weiteren E-Mails.", REPLY),
    # ----------------------------------------------------------------- Dutch
    ("nl", "Afmelden", LABEL),
    ("nl", "Uitschrijven", LABEL),
    ("nl", "Zou ik me afmelden voor de nieuwsbrief? Alvast dank.", REPLY),
    ("nl", "Beste, ik zou me graag uitschrijven op de mailinglijst.", REPLY),
    ("nl", "Ik maak bezwaar tegen de verwerking van mijn gegevens voor "
           "directmarketingdoeleinden", REGULATOR),
    # ---------------------------------------------------------------- French
    ("fr", "Se désabonner", LABEL),
    ("fr", "Désabonnement", LABEL),
    ("fr", "Pourriez-vous me désinscrire de la liste de diffusion svp ?",
     REPLY),
    ("fr", "Serait-il possible de me désabonner de cette liste de "
           "diffusion ?", REPLY),
    ("fr", "Je ne souhaite plus recevoir d'e-mails de votre part.", REPLY),
    ("fr", "je vous remercie de bien vouloir supprimer mes coordonnées de "
           "vos fichiers d'envoi de publicités", REGULATOR),
    ("fr", "DESABONNEMENT", LABEL),         # accents dropped in caps
    # --------------------------------------------------------------- Italian
    ("it", "Annulla iscrizione", LABEL),
    ("it", "Cancellami", LABEL),
    ("it", "Disiscriviti", LABEL),
    ("it", "non voglio più ricevere email", REPLY),
    ("it", "non voglio piu ricevere email", REPLY),
    ("it", "ho provato a cancellare il mio indirizzo email dalla lista",
     REPLY),
    ("it", "CANCELLAZIONE NEWSLETTER", LABEL),
    # --------------------------------------------------------------- Spanish
    ("es", "Darse de baja", LABEL),
    ("es", "Baja", LABEL),
    ("es", "Cancelar suscripción", LABEL),
    ("es", "POR FAVOR NO MAS CORREOS", REPLY),
    ("es", "Bórrenme de la lista", REPLY),
    ("es", "Hola me podrian borrar de su lista de correos por fa", REPLY),
    ("es", "No deseo recibir más publicidad.", REGULATOR),
    # ------------------------------------------------------------ Portuguese
    ("pt", "Cancelar inscrição", LABEL),
    ("pt", "Anular subscrição", LABEL),
    ("pt", "Descadastro", LABEL),
    ("pt", "Gentileza retirar o meu email deste circulo. Grato.", REPLY),
    # --------------------------------------------------------------- Swedish
    ("sv", "Avsluta prenumeration", LABEL),
    ("sv", "Avprenumerera", LABEL),
    ("sv", "avregistrera", REGULATOR),
    ("sv", "sluta skicka reklam till mig", REGULATOR),
    ("sv", "radera mina personuppgifter", REGULATOR),
    # ---------------------------------------------------------------- Danish
    ("da", "Frameld", LABEL),
    ("da", "Afmeld", LABEL),
    ("da", "Afmeld mig nyhedsbrevet tak", REPLY),
    ("da", "Jeg vil gerne trække mit samtykke tilbage.", REGULATOR),
    ("da", "Slet mig.", REGULATOR),
    # ------------------------------------------------------------- Norwegian
    ("no", "Meld deg av", LABEL),
    ("no", "Avslutt abonnement", LABEL),
    ("no", "Avmelding", LABEL),
    ("no", "Jeg vil reservere meg mot markedsføringen.", REGULATOR),
    ("no", "trekke samtykket", REGULATOR),
    # --------------------------------------------------------------- Finnish
    ("fi", "Peru tilaus", LABEL),
    ("fi", "Lopeta tilaus", LABEL),
    ("fi", "Poista minut postituslistalta.", REGULATOR),
    ("fi", "suoramarkkinointikielto", REGULATOR),
    ("fi", "Kiellän suoramarkkinoinnin.", REGULATOR),
    # -------------------------------------------------------------- Estonian
    ("et", "Soovin listist lahkuda", LABEL),
    ("et", "Tühista tellimus", LABEL),
    ("et", "Soovin uudiskirja tellimusest loobuda.", REGULATOR),
    ("et", "nõusoleku tagasivõtmine", REGULATOR),
    # ---------------------------------------------------------------- Polish
    ("pl", "Wypisz się", LABEL),
    ("pl", "Anuluj subskrypcję", LABEL),
    ("pl", "Zrezygnuj z subskrypcji", LABEL),
    ("pl", "Proszę o usunięcie moich danych osobowych z Państwa bazy",
     REGULATOR),
    ("pl", "Prosze o usuniecie moich danych osobowych z Panstwa bazy",
     REGULATOR),                            # diacritics dropped
    ("pl", "Nie wyrażam zgody na przetwarzanie moich danych osobowych",
     REGULATOR),
    ("pl", "Wnoszę sprzeciw wobec dalszego wykorzystywania mojego adresu "
           "email do celów marketingowych", REGULATOR),
    ("pl", "Cofam zgodę na przetwarzanie moich danych osobowych", TEMPLATE),
    ("pl", "Żądam zaprzestania przesyłania niezamówionej korespondencji "
           "handlowej", REGULATOR),
    # ----------------------------------------------------------------- Czech
    ("cs", "Odhlásit odběr", LABEL),
    ("cs", "Odhlasit odber", LABEL),        # diacritics dropped
    ("cs", "Odhlásit se", LABEL),
    ("cs", "Nepřeji si zasílat obchodní sdělení.", REGULATOR),
    ("cs", "Zrušit odběr", LABEL),
    # ---------------------------------------------------------------- Slovak
    ("sk", "Zrušiť odber", LABEL),
    ("sk", "Odhlásenie odberu", LABEL),
    ("sk", "Odhláste ma z odberu.", LABEL),
    ("sk", "Neželám si dostávať tieto správy.", REGULATOR),
    ("sk", "Namietam", REGULATOR),
    # ------------------------------------------------------------- Hungarian
    ("hu", "Leiratkozás", LABEL),
    ("hu", "Leiratkozas", LABEL),           # diacritics dropped
    ("hu", "Leiratkozom", LABEL),
    ("hu", "Kérem a leiratkozást.", LABEL),
    ("hu", "Nem kérek több hírlevelet", LABEL),
    ("hu", "kérem a személyes adataim törlését", TEMPLATE),
    # ------------------------------------------------------------ Lithuanian
    ("lt", "Atšaukti prenumeratą", LABEL),
    ("lt", "Atsisakyti naujienlaiškio", LABEL),
    ("lt", "Atsisakau naujienlaiskio prenumeratos", LABEL),
    ("lt", "Nebenoriu gauti laiškų į savo el. paštą", REPLY),
    ("lt", "Prašau pašalinti mane iš prenumeratorių sąrašo.", REGULATOR),
    ("lt", "atšaukti sutikimą", REGULATOR),
    # --------------------------------------------------------------- Latvian
    ("lv", "Atrakstīties no jaunumiem", LABEL),
    ("lv", "Atteikties no jaunumiem", LABEL),
    ("lv", "Anulēt abonementu", LABEL),
    ("lv", "atteikties no komerciālu paziņojumu saņemšanas", REGULATOR),
    # ------------------------------------------- Croatian / Serbian / Bosnian
    ("hr", "Odjava", LABEL),
    ("hr", "Odjava s mailing liste", LABEL),
    ("hr", "Otkaži pretplatu", LABEL),
    ("hr", "ulažem prigovor protiv izravnog marketinga", TEMPLATE),
    ("hr", "protivim se obradi osobnih podataka u svrhu izravnog marketinga",
     TEMPLATE),
    ("hr", "ovime povlačim navedeni pristanak", TEMPLATE),
    ("hr", "zahtijevam hitno brisanje osobnih podataka", TEMPLATE),
    ("hr", "Ne želim više primati vaše poruke.", LABEL),
    ("hr", "Ne zelim vise primati vase poruke.", LABEL),   # no diacritics
    # ------------------------------------------------------------- Slovenian
    ("sl", "Odjava od e-novic", LABEL),
    ("sl", "Odjavite se od prejemanja obvestil", LABEL),
    ("sl", "Želim izbrisati svoje podatke", REPLY),
    ("sl", "zahtevam izbris podatkov", REPLY),
    ("sl", "Ne želim več prejemati obvestil.", REPLY),
    ("sl", "ugovarjam obdelavi za namene neposrednega trženja", REGULATOR),
    # ----------------------------------------------------------------- Greek
    ("el", "Απεγγραφή", LABEL),
    ("el", "Διαγραφή από e-Newsletter", REGULATOR),
    ("el", "Θέλω να διαγραφώ από τη λίστα σας", REPLY),
    ("el", "ΔΙΑΓΡΑΨΤΕ ΜΕ ΤΩΡΑ", LABEL),
    ("el", "Αν θέλετε να ξεγραφτείτε απ' τη λίστα πατήστε εδώ", LABEL),
    ("el", "δεν επιθυμώ να λαμβάνω", REGULATOR),
    ("el", "δικαίωμα στη λήθη", REGULATOR),
)

#: (language, sentence, what it really means). REAL ordinary uses of words
#: that sit in the opt-out vocabulary. None of these may suppress anybody.
NOT_OPT_OUTS = (
    ("en", "Can you stop by our office next week?",
     "a visit"),
    ("en", "We had to stop the current vendor first, but this looks useful.",
     "stopping a supplier, not us"),
    ("en", "Please stop asking about the budget - I answered last week.",
     "a sharp answer, not a removal request"),
    ("en", "Is your platform GDPR compliant?",
     "a buying question - `gdpr` alone used to make this an unsubscribe"),
    ("en", "Could you remove the second line item from the quote?",
     "editing a quote"),
    ("en", "Sorry, I have to cancel Thursday's call. Can we do Friday?",
     "a reschedule, which is a live deal"),
    ("de", "Bitte melden Sie sich vom System ab und erneut an.",
     "log out and back in"),
    ("de", "Wir möchten die Lieferung für März abbestellen.",
     "cancelling a delivery"),
    ("de", "Der Wettkampf wird in Berlin ausgetragen.",
     "a competition is HELD in Berlin"),
    ("de", "Setzen Sie mich bitte auf den Verteiler.",
     "ADD me to the list - the exact opposite"),
    ("nl", "Ik moet me afmelden voor de meeting van donderdag.",
     "declining a meeting"),
    ("nl", "We gaan volgende maand een tender uitschrijven.",
     "issuing a tender"),
    ("fr", "Je suis en arrêt maladie jusqu'au 12.",
     "sick leave, in an out-of-office"),
    ("fr", "Nous avons dû supprimer deux postes cette année.",
     "cutting jobs"),
    ("it", "Basta che mi confermi la data.",
     "just confirm the date - a BUYING signal"),
    ("it", "Mi basta sapere il prezzo.",
     "I only need the price - a buying signal"),
    ("it", "Cancella l'appuntamento di giovedì.",
     "cancel Thursday's meeting"),
    ("es", "Estoy de baja hasta el 15 de marzo.",
     "sick leave, in an out-of-office"),
    ("es", "La tasa de conversión es baja este trimestre.",
     "the rate is low"),
    ("pt", "Vou sair às 18h, falamos amanhã.",
     "I'm leaving at six"),
    ("pt", "O relatório vai sair amanhã.",
     "the report comes out tomorrow"),
    ("sv", "Kan vi avsluta mötet 15:00?",
     "end the meeting"),
    ("sv", "Vi måste stoppa projektet.",
     "stop the project"),
    ("da", "Jeg framelder mig kurset.",
     "withdrawing from a course"),
    ("no", "Stopp der, det var ikke det jeg mente.",
     "stop there - an interjection"),
    ("no", "La oss avslutte møtet nå.",
     "end the meeting"),
    ("fi", "Lopetamme tuotannon ensi vuonna.",
     "we are ending production"),
    ("fi", "Peruuta kokous, en ehdi.",
     "cancel the meeting"),
    ("et", "Ma lahkun ettevõttest järgmisel kuul.",
     "I am leaving the company"),
    ("et", "Tühista kohtumine, palun.",
     "cancel the meeting"),
    ("pl", "Rezygnuję z udziału w spotkaniu.",
     "declining a meeting"),
    ("pl", "Nie jestem zainteresowany w tym kwartale.",
     "not interested - an answer about this quarter"),
    ("pl", "Potrzebuję wypis z KRS.",
     "a company-register extract"),
    ("pl", "Nie chcę tracić czasu, proszę o cennik.",
     "a HOT lead"),
    ("cs", "Musím se odhlásit z portálu a přihlásit znovu.",
     "log out of the portal"),
    ("cs", "Nemám zájem, děkuji.",
     "not interested"),
    ("cs", "Pravidelný odběr zboží nás zajímá.",
     "regular offtake of goods - a buying reply"),
    ("sk", "Musím zrušiť náš zajtrajší call.",
     "cancelling a call"),
    ("sk", "Nemám záujem.",
     "not interested"),
    ("hu", "Törölném a holnapi egyeztetést.",
     "cancelling tomorrow's meeting"),
    ("hu", "Köszönöm, nem kérek kávét.",
     "no coffee, thanks"),
    ("hu", "Nem aktuális most.",
     "not right now - a prospect to keep"),
    ("lt", "Turėsiu atsisakyti susitikimo.",
     "declining a meeting"),
    ("lt", "Nesutinku su jūsų vertinimu.",
     "I disagree with your assessment"),
    ("lv", "Diemžēl mums jāatsakās no šī piedāvājuma.",
     "declining the offer"),
    ("lv", "Atraksti man, kad vari.",
     "write back when you can - an ENGAGED reply"),
    ("hr", "Odjava radnika iz HZMO-a je u tijeku.",
     "deregistering an employee"),
    ("hr", "Ne želim gubiti vrijeme, pošaljite mi cijene.",
     "a HOT lead"),
    ("hr", "Možemo li ovo staviti na stop do idućeg kvartala?",
     "put it on hold until next quarter"),
    ("sl", "Ne želim demo, pošljite ceno.",
     "a HOT lead"),
    ("sl", "Dali smo stop na nove naročnine do januarja.",
     "a purchasing freeze"),
    ("el", "Ενδιαφερόμαστε, αλλά θέλουμε διαγραφή του τελευταίου όρου "
           "από τη σύμβαση.",
     "we're interested, but delete the last CLAUSE from the contract"),
)


class EveryOptOutIsRead(unittest.TestCase):
    """Requirement 1: a removal request in every language we send to."""

    def test_every_phrase_classifies_as_an_unsubscribe(self):
        for language, phrase, provenance in OPT_OUTS:
            with self.subTest(language=language, phrase=phrase):
                verdict = replies.classify(phrase)
                self.assertEqual(
                    verdict["classification"], replies.UNSUBSCRIBE,
                    f"[{language}/{provenance}] {phrase!r} read as "
                    f"{verdict['classification']!r} - somebody asking to be "
                    f"left alone would keep being mailed")

    def test_the_verdict_carries_the_words_that_were_matched(self):
        """Evidence comes from the ORIGINAL text, not the folded form.

        A person reading the alert has to see what was actually written. The
        fold is for matching only, and it is index-preserving so that this
        can be true.
        """
        verdict = replies.classify("Odhlásit odběr")
        self.assertEqual(verdict["evidence"], ["odhlásit odběr"])

    def test_every_language_we_send_to_appears_in_the_corpus(self):
        """A coverage table nothing tests is a list of good intentions."""
        covered = {language for language, _p, _s in OPT_OUTS}
        self.assertEqual(covered, set(replies.LANGUAGE_COVERAGE),
                         "a language is declared covered and has no phrase, "
                         "or has a phrase and is not declared")

    def test_the_corpus_is_not_secretly_english(self):
        """ISSUE-024's actual shape: a list that LOOKS multilingual."""
        non_english = [p for lang, p, _s in OPT_OUTS if lang != "en"]
        self.assertGreater(len(non_english), 100)
        self.assertGreater(len({lang for lang, _p, _s in OPT_OUTS}), 18)


class OrdinarySentencesAreNotOptOuts(unittest.TestCase):
    """The error that costs money, and it is not the smaller one.

    An unsubscribe is permanent and agency-wide from 2026-09-24. Suppressing
    somebody who wrote an ordinary sentence makes them unreachable by every
    client this agency has, and no operator can undo that from the outside.
    """

    def test_no_ordinary_sentence_is_read_as_a_removal_request(self):
        for language, sentence, meaning in NOT_OPT_OUTS:
            with self.subTest(language=language, sentence=sentence):
                verdict = replies.classify(sentence)
                self.assertNotEqual(
                    verdict["classification"], replies.UNSUBSCRIBE,
                    f"[{language}] {sentence!r} means {meaning} and was "
                    f"suppressed permanently, agency-wide. Evidence: "
                    f"{verdict.get('evidence')}")

    def test_no_ordinary_sentence_is_read_as_a_company_wide_stop(self):
        """ACCOUNT_DNC ranks above UNSUBSCRIBE and is worse still."""
        for language, sentence, meaning in NOT_OPT_OUTS:
            with self.subTest(language=language, sentence=sentence):
                self.assertNotEqual(
                    replies.classify(sentence)["classification"],
                    replies.ACCOUNT_DNC,
                    f"[{language}] {sentence!r} means {meaning}")


class TheRiskyTokensAreAnchoredToAClause(unittest.TestCase):
    """Tier B, and the whole reason there are two tiers.

    Every token in `STANDALONE_STOP_TOKENS` is an ordinary word in its own
    language. Each may be an opt-out when it is the WHOLE of a clause and
    never when it sits inside one.
    """

    def test_a_bare_token_alone_is_an_opt_out(self):
        for language, tokens in replies.STANDALONE_STOP_TOKENS.items():
            for token in tokens:
                with self.subTest(language=language, token=token):
                    self.assertEqual(
                        replies.classify(token)["classification"],
                        replies.UNSUBSCRIBE,
                        f"[{language}] a reply whose entire content is "
                        f"{token!r} was not read as an opt-out")

    def test_the_same_token_inside_a_sentence_is_not(self):
        """`_hits` would have matched every one of these. That is the bug."""
        carriers = (
            "We reviewed the %s question with our legal team and it is fine.",
            "Our own product has a %s flow that customers seem to like.",
            "I was asked about %s by a colleague this morning.",
        )
        for language, tokens in replies.STANDALONE_STOP_TOKENS.items():
            for token in tokens:
                for carrier in carriers:
                    sentence = carrier % token
                    with self.subTest(language=language, sentence=sentence):
                        self.assertNotEqual(
                            replies.classify(sentence)["classification"],
                            replies.UNSUBSCRIBE,
                            f"[{language}] {token!r} fired inside a sentence")

    def test_a_politeness_word_does_not_make_it_a_sentence(self):
        for phrase in ("please stop", "bitte abmelden", "prosim odhlasit",
                       "molim odjava", "kiitos lopeta"):
            with self.subTest(phrase=phrase):
                self.assertEqual(
                    replies.classify(phrase)["classification"],
                    replies.UNSUBSCRIBE)

    def test_a_longer_clause_containing_the_token_is_not_an_opt_out(self):
        """The distinction the clause anchor actually makes."""
        for phrase in ("please stop asking",
                       "we will stop the trial in December",
                       "I had to stop the integration work"):
            with self.subTest(phrase=phrase):
                self.assertNotEqual(
                    replies.classify(phrase)["classification"],
                    replies.UNSUBSCRIBE)


class TheFoldIsSelfTested(unittest.TestCase):
    """The redaction-filter discipline: check the filter against every value.

    A pattern written with a diacritic would be matched against text that has
    had its diacritics removed, so it could never fire - and a pattern that
    can never fire looks exactly like a language nobody writes an opt-out in.
    """

    def test_every_opt_out_pattern_is_already_in_folded_form(self):
        for language, patterns in replies.OPT_OUT_PHRASES.items():
            for pattern in patterns:
                with self.subTest(language=language, pattern=pattern):
                    self.assertEqual(
                        replies.fold(pattern), pattern,
                        f"[{language}] this pattern is not folded, so it can "
                        f"never match folded text")

    def test_every_standalone_token_is_already_in_folded_form(self):
        for language, tokens in replies.STANDALONE_STOP_TOKENS.items():
            for token in tokens:
                with self.subTest(language=language, token=token):
                    self.assertEqual(replies.fold(token), token)

    def test_the_fold_never_changes_a_string_length(self):
        """Evidence is sliced from the original by the match's own offsets."""
        for _language, phrase, _s in OPT_OUTS:
            with self.subTest(phrase=phrase):
                self.assertEqual(len(replies.fold(phrase)), len(phrase))

    def test_the_fold_leaves_greek_in_greek(self):
        """Transliteration is a guess about spelling. Accents are not."""
        self.assertEqual(replies.fold("Διαγραφή"), "διαγραφη")

    def test_the_fold_reaches_every_diacritic_in_the_corpus(self):
        """Folded and unfolded spellings of one phrase are one request."""
        pairs = (("Odhlásit odběr", "Odhlasit odber"),
                 ("Leiratkozás", "Leiratkozas"),
                 ("Proszę o usunięcie", "Prosze o usuniecie"),
                 ("Ne želim više primati", "Ne zelim vise primati"),
                 ("Atšaukti prenumeratą", "Atsaukti prenumerata"))
        for accented, plain in pairs:
            with self.subTest(accented=accented):
                self.assertEqual(replies.fold(accented), replies.fold(plain))


class TheLanguagesAreDerivedFromWhereWeActuallySend(unittest.TestCase):
    """Requirement: derive the languages from the live supply, not a guess.

    `work/` is gitignored and holds real client data, so this test does not
    require it. When it is present the assertion is made against the real
    sourced pool; when it is not, the test says so rather than passing
    silently - a coverage check that quietly checks nothing is the failure
    mode this repository names most often.
    """

    #: Measured 2026-09-24 from `work/qualified-supply.jsonl`, 32,951 rows.
    MEASURED_COUNTRIES = {
        "United States", "United Kingdom", "France", "Netherlands",
        "Australia", "Spain", "Italy", "Sweden", "Germany", "Poland",
        "Denmark", "Switzerland", "Belgium", "Norway", "Finland", "Ireland",
        "Portugal", "Austria", "New Zealand", "Canada",
    }

    COUNTRY_LANGUAGE = {
        "United States": "en", "United Kingdom": "en", "Ireland": "en",
        "Australia": "en", "New Zealand": "en", "Canada": "en",
        "Germany": "de", "Austria": "de", "Switzerland": "de",
        "France": "fr", "Belgium": "nl", "Netherlands": "nl",
        "Spain": "es", "Italy": "it", "Portugal": "pt", "Sweden": "sv",
        "Denmark": "da", "Norway": "no", "Finland": "fi", "Poland": "pl",
    }

    def test_every_country_on_the_live_supply_has_a_covered_language(self):
        for country in self.MEASURED_COUNTRIES:
            with self.subTest(country=country):
                language = self.COUNTRY_LANGUAGE[country]
                self.assertIn(language, replies.LANGUAGE_COVERAGE)

    def test_the_supply_has_not_grown_a_country_nobody_covered(self):
        """Reads the real file when it is there. Skips loudly when it is not."""
        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "work", "qualified-supply.jsonl")
        if not os.path.exists(path):
            self.skipTest(
                "work/qualified-supply.jsonl is absent - this worktree has no "
                "copy of the live supply, so the coverage table is checked "
                "against the 2026-09-24 measurement above and NOT against "
                "today's pool")
        found = set()
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if row.get("country"):
                    found.add(row["country"])
        new = found - self.MEASURED_COUNTRIES
        self.assertEqual(
            new, set(),
            f"the estate now sources {sorted(new)}, which nothing in "
            f"replies.LANGUAGE_COVERAGE was written for. ISSUE-024 is this "
            f"exact shape: a safety list that was complete when it was "
            f"written")

    def test_the_partial_languages_say_what_is_missing(self):
        """A coverage claim with no caveat is the one nobody checks."""
        for language, (name, countries, note) in \
                replies.LANGUAGE_COVERAGE.items():
            with self.subTest(language=language):
                self.assertTrue(name and countries and note)
                if note != "full":
                    self.assertTrue(note.startswith("partial:"),
                                    f"{language}: {note!r} is neither full "
                                    f"nor a stated partial")


if __name__ == "__main__":
    unittest.main()
