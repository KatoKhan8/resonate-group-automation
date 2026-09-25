"""The span filters, asserted on the strings they were each written for.

Every case below is a REAL span this extractor produced on the 2026-09-24
crawl. The PASS cases are quotes that went out; the FAIL cases are the ones a
filter was added to catch, each with the reason it must be caught for. A
filter that rejects the seam and also rejects `based in Clerkenwell, East
London` has not helped, so the survivors are asserted too.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "scripts"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import lane_h_pack_grounded_render as H
from src import copylint

MUST_PASS = [
    "We design, build and deliver creative events and experiences that "
    "trigger the right vibe",
    "Founded in 2010 in Oldenburg, Germany, Affiliprint launched with a bold "
    "vision: to bridge the gap between online precision and offline impact",
    "An independent creative agency based in Clerkenwell, East London",
    "We're an established FMCG agency with a start-up mentality and a team "
    "with exceptional talent at its core",
    "Delivering the tastiest world food experiences in over 2.000 ethnics "
    "stores in the EU",
    "We are a data- and AI-driven growth engine for app publishers",
    "Paris-based creative agency offering a complete in-house process from "
    "Creative Direction and Production to Post Production delivering "
    "beautifully crafted and cohesive results at every stage",
    "Shomei is built around creative minds with decades of experience, sharp "
    "instincts and a shared ability to turn complexity into clarity",
]

MUST_FAIL = [
    ("Imagination creates the new Exceeding your expectations and ensuring "
     "you value with undeniably unique content that captivates your audience",
     "glued sentence"),
    ("And we know how to bring the two together: with ideas that resonate "
     "messages that work", "opens on a conjunction"),
    ("We handle the funding We are a data- and AI-driven growth engine for "
     "app publishers", "glued sentence"),
    ("Contact Us Shomei is built around creative minds with decades of "
     "experience and sharp instincts", "opens on navigation"),
    ("The store will not work correctly in the case when cookies are "
     "disabled", "boilerplate"),
    ("Aktuellt Kontakt Your browser does not support the video tag",
     "boilerplate"),
    ("& BEVERAGE Delivering the tastiest world food experiences in over "
     "2.000 ethnics stores", "starts mid-sentence"),
    ("Dance: Decades of Hits, we crafted a timeless mixtape inspired logo",
     "starts mid-sentence"),
    ("We are Fotolight Fotolight is a production company with 70 years of "
     "experience in outdoor communication", "glued repeat"),
    ("Automotive Education Hospitals Commercial Hotels Leisure Pubs "
     "Restaurants Retail Cladding", "heading run"),
    # GERMAN CAPITALISES ITS NOUNS, SO THE GLUED-SENTENCE RULE FIRES ON ALL
    # GERMAN PROSE BEFORE THE LANGUAGE RULE EVER SEES IT. `klare Strategie`
    # looks exactly like a heading that ran into the sentence behind it. This
    # is a REAL LIMIT, not a bug in this case: it means German spans are
    # counted under "no quotable span" rather than under "not in English",
    # and that the --allow-non-english lever is worth MORE than the 59 it
    # reports. Asserted here so it is recorded rather than rediscovered.
    ("Eigene Familienforschung, klare Strategie und starke Kreation - fuer "
     "fundierte Markenentscheidungen.", "glued sentence"),
    # `wir Wir` is an adjacent repeat, which is caught before the nav rule.
    ("Startseite Das sind wir Wir leben Community Wir lieben innovative Apps "
     "und tolle Web-Ideen", "glued repeat"),
]

bad = 0
for text in MUST_PASS:
    why = H._quality(text, copylint)
    if why:
        bad += 1
        print("FAIL  a good quote was rejected as %-20s %r" % (why, text[:70]))
    else:
        print("ok    quotable                                %r" % text[:60])
print()
for text, want in MUST_FAIL:
    why = H._quality(text, copylint)
    if why != want:
        bad += 1
        print("FAIL  expected %-22s got %-22s %r" % (want, why, text[:60]))
    else:
        print("ok    rejected as %-22s %r" % (why, text[:52]))

print()
lang_cases = [
    ("We design, build and deliver creative events and experiences", "en"),
    ("Konzeption all unserer Projekte denken wir zunaechst an Sie", "de"),
    # One stopword hit is not evidence of a language. `unknown` is the
    # fail-closed answer and it HOLDS the lead, which is correct.
    ("Doorbraken beginnen waar verschillende ideeen elkaar raken", "unknown"),
    ("Als strategisch creatief bureau brengt DPI werelden samen en wij zijn "
     "er voor onze klanten", "nl"),
]
for text, want in lang_cases:
    got, scores = H.language_of(text)
    mark = "ok   " if got == want else "FAIL "
    if got != want:
        bad += 1
    print("%s language %-8s want %-8s %r  %s"
          % (mark, got, want, text[:46],
             {k: v for k, v in scores.items() if v}))

print("\n%d failure(s)" % bad)
raise SystemExit(1 if bad else 0)
