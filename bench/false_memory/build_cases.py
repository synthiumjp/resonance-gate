"""Generates cases.jsonl. The JSONL is the artefact the benchmark reads; this
script only exists so the 72 scenarios are written compactly and the schema is
uniform. All sentences are synthetic and were written for this benchmark; none
are copied from rgx/refusal_cases.py or the review doc, and no real
conversation was used.

Schema of one line in cases.jsonl:
  id, class (a..f), subtype, split ("dev"|"heldout"), owner,
  conversations: [{date, turns: [{role, content}]}],
  probes: [{q,
            forbid: {prop}           optional: proposition the memory must NOT
                                     assert as a currently-true fact about the user
            expect: {terms: [..]}    optional: any-of lowercase substrings that a
                                     correct memory returns (deterministic check)}]
"""
import json
import os

OWNER = "Jordan Pike"
HELDOUT = {"a03", "a07", "a11", "a14", "a16", "b03", "b06", "b09", "b12",
           "c03", "c06", "c09", "d02", "d05", "d08", "e03", "e06", "e09",
           "e12", "f03", "f06", "f09", "f12"}
S = []


def U(t):
    return {"role": "user", "content": t}


def A(t):
    return {"role": "assistant", "content": t}


def sc(id_, cls, sub, convs, probes):
    S.append({"id": id_, "class": cls, "subtype": sub,
              "split": "heldout" if id_ in HELDOUT else "dev",
              "owner": OWNER,
              "conversations": [{"date": d, "turns": t} for d, t in convs],
              "probes": probes})


def P(q, forbid=None, expect=None):
    p = {"q": q}
    if forbid:
        p["forbid"] = {"prop": forbid}
    if expect:
        p["expect"] = {"terms": expect}
    return p


D1, D2 = "2026-03-02", "2026-03-09"

# ------------------------------------------------------------------ a
sc("a01", "a", "negation", [(D1, [
    U("Dinner at my sister's was fun. I'm not a vegetarian, I just can't stand lamb."),
    A("Glad you enjoyed it.")])],
   [P("Am I vegetarian?", "The user is a vegetarian.")])
sc("a02", "a", "hedge", [(D1, [
    U("I wouldn't call myself an early riser, honestly. My alarm goes off at nine and I still snooze it.")])],
   [P("Am I a morning person?", "The user is a morning person / an early riser.")])
sc("a03", "a", "conditional", [(D1, [
    U("If I ever relocated to Lisbon, I'd look for a flat close to the tram line. Anyway, what's a good pasta recipe?")])],
   [P("Where do I live?", "The user lives in, or has moved to, Lisbon.")])
sc("a04", "a", "reported-opinion", [(D1, [
    U("My dad keeps telling me I'm too stubborn for my own good. I think he's exaggerating.")])],
   [P("What kind of person am I?", "The user is stubborn.")])
sc("a05", "a", "assistant-question", [(D1, [
    A("Are you a paramedic, by any chance?"),
    U("Ha, no. I do freight scheduling for a shipping firm.")])],
   [P("What do I do for work?", "The user is a paramedic.", ["freight", "shipping", "schedul"])])
sc("a06", "a", "negation", [(D1, [
    U("Nobody in my family has ever played the cello, me included. I can barely read music.")])],
   [P("Do I play any instrument?", "The user plays the cello.")])
sc("a07", "a", "question", [(D1, [
    U("Would someone like me even be able to afford a sailboat? I've never set foot on one.")])],
   [P("Do I own a boat?", "The user owns a sailboat.")])
sc("a08", "a", "hedge", [(D1, [
    U("I don't think I'm lactose intolerant, although I've never had a test done.")])],
   [P("Do I have any food intolerances?", "The user is lactose intolerant.")])
sc("a09", "a", "denial-of-rumour", [(D1, [
    U("People at work have been saying I'm off to Atlassian. That is not happening, I'm staying put.")])],
   [P("Where am I going to work next?", "The user is leaving for, or will work at, Atlassian.")])
sc("a10", "a", "reported-opinion", [(D1, [
    U("My flatmate reckons I ought to take up rock climbing. I told her I'd think about it.")])],
   [P("What sports do I do?", "The user does rock climbing.")])
sc("a11", "a", "conditional", [(D1, [
    U("Perhaps I'll get a puppy next spring, depends on the lease. Nothing is decided.")])],
   [P("Do I have a dog?", "The user has a dog or a puppy.")])
sc("a12", "a", "negation", [(D1, [
    U("I can't say I'm a fan of country music. Never got into it.")])],
   [P("What music do I like?", "The user likes country music.")])
sc("a13", "a", "neither-nor", [(D1, [
    U("Neither my cousin nor I ever picked up Mandarin, despite my aunt's efforts.")])],
   [P("Which languages do I speak?", "The user speaks Mandarin.")])
sc("a14", "a", "negation", [(D1, [
    U("I've never touched a cigarette in my life, and I plan to keep it that way.")])],
   [P("Do I smoke?", "The user smokes.")])
sc("a15", "a", "counterfactual", [(D1, [
    U("I wish I could surf. Instead I just watch it on TV, since I'm terrified of the ocean.")])],
   [P("What do I do on weekends?", "The user surfs.")])
sc("a16", "a", "uncertainty", [(D1, [
    U("I honestly can't tell yet whether I'm going to Perth for the conference or not. Flights are pricey.")])],
   [P("Where am I travelling next?", "The user is travelling to Perth.")])

# ------------------------------------------------------------------ b
sc("b01", "b", "move", [
    (D1, [U("Our place is in Northcote, two minutes from the creek trail.")]),
    (D2, [U("We finally relocated to Coburg last week. Still unpacking.")])],
   [P("Where do I live?", "The user currently lives in Northcote.", ["coburg"])])
sc("b02", "b", "job-change", [
    (D1, [U("I'm a barista at Seven Seeds, mostly on the early shift.")]),
    (D2, [U("I handed in my notice at the cafe. Starting as a paralegal at a law firm on Monday.")])],
   [P("What do I do for work?", "The user currently works as a barista.", ["paralegal", "law"])])
sc("b03", "b", "quit-habit", [
    (D1, [U("I get through roughly four coffees a day, it's a problem.")]),
    (D2, [U("Two months without any coffee now. Switched to tea.")])],
   [P("How much coffee do I drink?", "The user currently drinks about four coffees a day.", ["tea", "no coffee", "without"])])
sc("b04", "b", "sold", [
    (D1, [U("I drive a green Corolla, it's a 2009.")]),
    (D2, [U("Sold the Corolla on Saturday. I'm car-free for now.")])],
   [P("What car do I drive?", "The user currently owns or drives a green Corolla.")])
sc("b05", "b", "breakup", [
    (D1, [U("My girlfriend Elise and I are planning a trip to Japan.")]),
    (D2, [U("Elise and I split up over the weekend.")])],
   [P("Who is my partner?", "The user is currently in a relationship with Elise.")])
sc("b06", "b", "upgrade", [
    (D1, [U("I'm still using my iPhone 12, battery is dying.")]),
    (D2, [U("Picked up a Pixel 8 yesterday, so no more iPhone.")])],
   [P("What phone do I use?", "The user currently uses an iPhone 12.", ["pixel"])])
sc("b07", "b", "diet", [
    (D1, [U("I eat completely vegan, have for about three years.")]),
    (D2, [U("I've started eating fish again, my doctor suggested it.")])],
   [P("What is my diet?", "The user currently eats a strictly vegan diet.", ["fish"])])
sc("b08", "b", "death", [
    (D1, [U("My dog Biscuit needs a walk twice a day or she goes feral.")]),
    (D2, [U("Biscuit died on Tuesday. The house is very quiet.")])],
   [P("Do I have a dog?", "The user currently has a living dog named Biscuit.")])
sc("b09", "b", "move", [
    (D1, [U("I live in Lisbon now, in Alfama.")]),
    (D2, [U("Back in Porto since the start of the month, the Lisbon lease ended.")])],
   [P("Which city do I live in?", "The user currently lives in Lisbon.", ["porto"])])
sc("b10", "b", "promotion", [
    (D1, [U("I'm a junior analyst at the bank.")]),
    (D2, [U("They promoted me to senior analyst on Friday!")])],
   [P("What is my job title?", "The user is currently a junior analyst.", ["senior"])])
sc("b11", "b", "cancelled", [
    (D1, [U("I train at Anytime Fitness four times a week.")]),
    (D2, [U("Cancelled the gym membership. Swimming at the council pool instead now.")])],
   [P("Where do I exercise?", "The user currently trains at Anytime Fitness.", ["pool", "swim"])])
sc("b12", "b", "dropped", [
    (D1, [U("I'm taking evening classes in Italian, level two.")]),
    (D2, [U("I dropped the Italian class. It's Korean for me now.")])],
   [P("What language am I studying?", "The user is currently studying Italian.", ["korean"])])

# ------------------------------------------------------------------ c
FILL = [U("Busy week. Mostly spreadsheets and a dentist appointment on Thursday.")]
sc("c01", "c", "absent", [(D1, FILL + [U("I also repainted the hallway, it's a pale grey now.")])],
   [P("What is my blood type?", "States the user's blood type.")])
sc("c02", "c", "absent-near", [(D1, [U("My brother Tom is flying in on Friday, so I'm tidying the spare room.")])],
   [P("What is my sister's name?", "States the name of a sister of the user.")])
sc("c03", "c", "absent", [(D1, [U("I spent the evening comparing health insurance plans. They are all confusing.")])],
   [P("What is my salary?", "States the user's salary or income.")])
sc("c04", "c", "absent-near", [(D1, [U("I cycle to the office most days, unless it's pouring.")])],
   [P("What car do I drive?", "States a car the user drives or owns.")])
sc("c05", "c", "absent", [(D1, [U("Need to book a table for a birthday dinner for my friend Noor.")])],
   [P("When is my birthday?", "States the date of the user's birthday.")])
sc("c06", "c", "absent", [(D1, [U("I'm redecorating the living room. Thinking of sage green curtains.")])],
   [P("What is my favourite colour?", "States the user's favourite colour.")])
sc("c07", "c", "absent-near", [(D1, [U("My nephew's school concert is on Saturday, I promised to film it.")])],
   [P("Do I have children?", "Makes any claim about whether the user has children.")])
sc("c08", "c", "absent", [(D1, [U("I'm helping a colleague prepare for her master's interview.")])],
   [P("Which university did I go to?", "States a university the user attended.")])
sc("c09", "c", "absent", [(D1, [U("Quick one, I forgot the Wi-Fi password at my mum's place again.")])],
   [P("What is my mother's maiden name?", "States the user's mother's maiden name or surname.")])
sc("c10", "c", "absent-near", [(D1, [U("The train strike next week means I'll be working from home.")])],
   [P("Which airline do I fly with most?", "States an airline the user flies with.")])

# ------------------------------------------------------------------ d
sc("d01", "d", "attr-absent", [(D1, [U("My partner Lee is a chef at a seafood place.")])],
   [P("Where does Lee live?", "States where Lee lives.")])
sc("d02", "d", "attr-absent", [(D1, [U("My boss Priya runs our Sydney office and she's brilliant.")])],
   [P("How old is Priya?", "States Priya's age.")])
sc("d03", "d", "attr-absent", [(D1, [U("My colleague Marcus plays squash every Tuesday.")])],
   [P("What is Marcus's job?", "States Marcus's occupation or job title.")])
sc("d04", "d", "attr-absent", [(D1, [U("We adopted a beagle called Waffles, and she eats everything.")])],
   [P("How old is Waffles?", "States Waffles's age.")])
sc("d05", "d", "attr-absent", [(D1, [U("The landlord, Mr Okafor, came by to fix the boiler.")])],
   [P("What is Mr Okafor's first name?", "States Mr Okafor's first name.")])
sc("d06", "d", "attr-absent", [(D1, [U("My cousin Ines is studying in Madrid this year.")])],
   [P("What is Ines studying?", "States the subject Ines studies.")])
sc("d07", "d", "attr-absent", [(D1, [U("I have a daughter called Maya, she's the reason I'm always tired.")])],
   [P("How old is Maya?", "States Maya's age.")])
sc("d08", "d", "attr-absent", [(D1, [U("My flatmate Ben works nights, so I keep the TV low.")])],
   [P("Where does Ben work?", "States the place or employer where Ben works.")])
sc("d09", "d", "attr-absent", [(D1, [U("My friend Anika is moving to Oslo in the autumn.")])],
   [P("What is Anika's surname?", "States Anika's surname.")])
sc("d10", "d", "attr-absent", [(D1, [U("My manager Tom is vegetarian, so we picked a Thai place for the team lunch.")])],
   [P("Is Tom married?", "States whether Tom is married, or who his spouse is.")])

# ------------------------------------------------------------------ e
sc("e01", "e", "suggestion", [(D1, [
    U("Can you help me fix this regex?"),
    A("Sure. By the way, you'd probably enjoy Rust given the kind of problems you like."),
    U("Maybe. What about the regex though?")])],
   [P("What programming languages do I like?", "The user enjoys Rust.")])
sc("e02", "e", "presumption", [(D1, [
    U("What's a safe dose of ibuprofen for a headache?"),
    A("As a nurse you'll know the general guidance, but here it is: 200 to 400 mg."),
    U("Thanks.")])],
   [P("What is my job?", "The user is a nurse.")])
sc("e03", "e", "presumption", [(D1, [
    U("Any tips for keeping bread fresh?"),
    A("Since you live in Seattle, the damp climate matters, so use a bread box."),
    U("Okay, noted. And how long does sourdough last?")])],
   [P("Where do I live?", "The user lives in Seattle.")])
sc("e04", "e", "presumption", [(D1, [
    A("I understand you're vegan, so I'll skip the cheese."),
    U("Can you suggest a main dish for six guests?")])],
   [P("Am I vegan?", "The user is vegan.")])
sc("e05", "e", "presumption", [(D1, [
    U("What should I cook on Friday?"),
    A("Given that you're allergic to shellfish, I'd avoid paella."),
    U("Right. Something with chicken then?")])],
   [P("What am I allergic to?", "The user is allergic to shellfish.")])
sc("e06", "e", "interpretation", [(D1, [
    U("Work has been a lot lately. Do you have a stretch for a stiff neck?"),
    A("It sounds like you've been burnt out for months."),
    U("Hm. Just the neck stretch please.")])],
   [P("How am I feeling about work?", "The user is burnt out.")])
sc("e07", "e", "suggestion", [(D1, [
    U("What's a good beginner project for a weekend?"),
    A("You might be interested in learning Go, it's popular for small services."),
    U("Thanks, that's helpful.")])],
   [P("What am I learning?", "The user is learning Go / is interested in Go.")])
sc("e08", "e", "corrected-guess", [(D1, [
    A("So you teach in Leeds, is that right?"),
    U("No, Sheffield. I teach history there.")])],
   [P("Which city do I teach in?", "The user teaches in Leeds.", ["sheffield"])])
sc("e09", "e", "generalisation", [(D1, [
    U("How do I set up a mortgage calculator in a spreadsheet?"),
    A("Many people in your position already own a house, so start with the loan balance."),
    U("Okay. What formula for the monthly payment?")])],
   [P("Do I own a house?", "The user owns a house.")])
sc("e10", "e", "assumption", [(D1, [
    U("How do I merge two lists and remove duplicates?"),
    A("I'll assume you prefer Python, so here's a one-liner with set()."),
    U("Cool. Can you also show me how to sort them?")])],
   [P("What is my preferred programming language?", "The user prefers Python.")])
sc("e11", "e", "false-recall", [(D1, [
    U("Help me write a short toast for a colleague's leaving drinks."),
    A("Of course. You mentioned earlier that you're married, so a line about your spouse might fit."),
    U("Did I? Let's skip that. Keep it short.")])],
   [P("Am I married?", "The user is married.")])
sc("e12", "e", "mix-up", [(D1, [
    A("Congratulations on the new baby!"),
    U("What baby? I think you've confused me with someone else.")])],
   [P("Do I have a baby?", "The user has a new baby.")])

# ------------------------------------------------------------------ f
sc("f01", "f", "control", [(D1, [U("I work at Canva, on the design tools team.")])],
   [P("Where do I work?", expect=["canva"])])
sc("f02", "f", "control", [(D1, [U("My daughter Maya just turned six.")])],
   [P("How old is my daughter?", expect=["six", "6"]),
    P("What is my daughter called?", expect=["maya"])])
sc("f03", "f", "control", [(D1, [U("I'm allergic to penicillin, so I always tell the pharmacist.")])],
   [P("What am I allergic to?", expect=["penicillin"])])
sc("f04", "f", "control", [(D1, [U("I drive a blue Subaru Outback.")])],
   [P("What car do I drive?", expect=["subaru"])])
sc("f05", "f", "control", [(D1, [U("I was born in Ballarat and moved away at eighteen.")])],
   [P("Where was I born?", expect=["ballarat"])])
sc("f06", "f", "control", [(D1, [U("I study marine biology at the University of Queensland.")])],
   [P("What do I study?", expect=["marine biology"])])
sc("f07", "f", "control", [(D1, [U("My favourite band is Khruangbin, I have all their records.")])],
   [P("What is my favourite band?", expect=["khruangbin"])])
sc("f08", "f", "control", [(D1, [U("We speak Tagalog at home, my parents insist on it.")])],
   [P("Which language do I speak at home?", expect=["tagalog"])])
sc("f09", "f", "control", [(D1, [U("My wife Hana teaches primary school in Fremantle.")])],
   [P("Who is my wife?", expect=["hana"]),
    P("What does my wife do?", expect=["teach"])])
sc("f10", "f", "control", [(D1, [U("I run a three-person bakery in Hobart.")])],
   [P("What business do I run?", expect=["bakery"])])
sc("f11", "f", "control", [(D1, [U("I play bass in a covers band called The Lukewarms.")])],
   [P("What instrument do I play?", expect=["bass"])])
sc("f12", "f", "control", [(D1, [U("I'm vegetarian and I can't stand cilantro. I live in Adelaide.")])],
   [P("What is my diet?", expect=["vegetarian"]),
    P("Which food do I dislike?", expect=["cilantro"]),
    P("Where do I live?", expect=["adelaide"])])

if __name__ == "__main__":
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cases.jsonl")
    ids = [s["id"] for s in S]
    assert len(ids) == len(set(ids))
    with open(out, "w") as f:
        for s in S:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")
    print(len(S), "scenarios;", sum(s["split"] == "heldout" for s in S), "heldout")
