# Conversation classification criteria

*[Leer en español](classification-criteria.es.md)*

These are the agreed definitions, and the source of truth for the classifier's implementation.
The figures come from a real sample file (1–2 Aug 2026, 3,219 conversations); the data in this
repository is synthetic.

> **Note on configurability.** This document describes the default schema (the first campaign the
> tool was built for). Campaigns can now define their own categories, indicators and decision tree
> (see `analysis/schema.py`), so the categories below are an example of the method rather than a
> hard-coded list.

---

## 1. Categories

Each conversation gets **one** `categoria_final`, out of these four:

| Category | Definition | How it is decided |
|---|---|---|
| `SIN_RESPUESTA` (no reply) | The customer never wrote. It is an unanswered bulk message, **not** a rejection. | Hard rule |
| `INTERESADO` (interested) | Stated purchase intent or asked to move forward with an agent. | Hard rule |
| `RESOLVIO_DUDAS` (got answers) | Asked for information about the product, credit line, rates or terms. | **AI** |
| `NO_INTERESADO` (not interested) | Explicitly said they are not interested. | Hard rule |

### 1.1 `SIN_RESPUESTA`

The customer sent no message at all (`0` messages with `sender = 'CUSTOMER'`).

These are the proactive bulk messages nobody answered: **3,002 of 3,219 conversations (93.3%)** in
the sample. They are kept separate on purpose: they fit none of the other three categories and, if
mixed in, would distort every indicator.

### 1.2 `INTERESADO`

**Criterion (revised after manual validation): the customer TOOK the credit line**, i.e. completed
the request. Stating intent without following through is **not** enough.

> In the business owner's words: *"someone is marked as interested when they take the credit line;
> if they ask questions but don't take it, or don't say they want it, they're not interested — they
> got their questions answered"*.

**Two levels** are recorded, because they answer different business questions:

| Flag | Meaning | Signal | Defines the category? |
|---|---|---|---|
| `interes_declarado` (declared interest) | Showed initial intent | Tapped `Quiero usar mi cupo` ("I want to use my credit line") or `Hablar con un asesor` ("Talk to an agent") | **No.** Informational only |
| `interes_confirmado` (confirmed interest) | **Followed through**: the request was registered and escalated to an agent | The bot sent `✅ Hemos registrado tu interés` ("We have registered your interest"), or the AI detects the customer agreed to go ahead with the purchase | **Yes** |

`categoria_final = INTERESADO` only when `interes_confirmado` is true.

These are **not** confirmed interest (all are real cases from the sample):

- Asking about prices or instalments in detail: *"I'm interested in applying for four million, how
  much would I pay per month"* → that is a **question**, not a purchase.
- Future interest: *"a bit later, I'll get back to you when I'm doing better"*.
- Tapping `Quiero usar mi cupo` at the start and abandoning the conversation.

> Business note: customers who stated intent but did not follow through are a drop-off indicator.
> The `interes_declarado` flag measures them without counting them as interested.

### 1.3 `RESOLVIO_DUDAS` (flag: `busco_informacion`, "looked for information")

The customer **obtained information** about the product, the credit line, rates, terms, partner
stores or points of sale.

**Agreed criterion (broadened after manual validation): it counts whether they asked explicitly or
obtained the information by moving through the bot's guided flow.** That is why the flag is called
`busco_informacion` and not `hizo_preguntas` ("asked questions"): requiring a formal question left
out cases in which the customer did get an answer.

It does not require the bot to have answered well either — the category measures what the customer
was looking for, not the bot's performance. Bot failures are tracked separately in `bot_no_resolvio`.

**Includes** (real examples from the sample; none of them has a `?`):

```
Explicit questions:
  "Que intereses manejan"  (what interest do you charge)
  "Cuanto es mi cupo"      (how much is my credit line)
  "Los intereses"          (the interest)
  "A qué puntaje es el interés" (what's the interest rate)

Information obtained without asking, inside the guided flow:
  "Un televisor" (a TV) → "Tienda Central o ElectroHogar" → the bot tells them which partners sell it
  "Efectivo" (cash)     → the bot clarifies that the credit line does not pay out cash
```

**Explicitly excludes:**

- Greetings: `"Hola"`, `"Buenos días"`, `"Buen día"`
- Thanks and polite closings: `"Gracias"`, `"Muchas gracias"`, `"Ok"`
- Answers to the rejection survey (see 1.4)
- Menu buttons (`Quiero usar mi cupo`, etc.), which express intent, not a query
- Anything the **bot** says: the bot asks questions all the time (*"do you have a product in
  mind?"*), and those questions are not the customer's

**Why this category needs AI:** only **6%** of customers use a question mark, while **48%** write
free text without one. A regex looking for `?` would catch about 14 of the ~70 real questions. And
more patterns do not fix it: `"Los intereses"` is syntactically indistinguishable from a passing
remark — what makes it a question is the conversational context.

### 1.4 `NO_INTERESADO`

Explicit rejection. Signals:

- The customer tapped the `No estoy interesado` ("I'm not interested") button (112 exact
  occurrences), **or**
- The bot sent the reasons survey: `Lamentamos que por ahora no desees...` ("We're sorry you don't
  want to... for now").

Answers to that survey (digits `1`–`6`, for *1️⃣ I don't need to buy anything*, … *6️⃣ I had a bad
experience*) are treated as **part of the same rejection event**, never as questions.

`NO_INTERESADO` is also the default category: if the customer replied but neither took the credit
line nor asked anything, they are not interested. That includes people who only said hello or
thanks, and business auto-responders (see 1.5).

### 1.5 Business auto-responders (`es_autorespondedor`)

Some numbers in the campaign list **belong to businesses rather than people**, and their WhatsApp
auto-responder replies to the bot. Real examples (business names changed):

```
"Gracias por comunicarte con Consultorio Dental Sonrisas. ¿Cómo podemos ayudarte?"
"¡Bienvenid@ a Ferretería El Tornillo. ¿Como podemos ayudarte?"
"...recuerda que nuestro horario administrativo es de 7:30 a 4:00 pm"
```

That *"¿Cómo podemos ayudarte?"* ("How can we help you?") was mistaken for a customer question and
inflated `RESOLVIO_DUDAS`. These replies are now detected by rule, classified as `NO_INTERESADO` and
flagged with `es_autorespondedor`.

**Business value:** the flag lists the contacts that should be removed from the campaign list,
because they will never convert.

> **Careful — an auto-responder does not always mean nobody is there.** In one real case the
> business auto-replied and **then a person kept writing** (asked for the catalogue and about a cash
> advance). So the rule only classifies directly when the auto-reply is the **only** thing there;
> if any other customer text remains, the conversation goes to the AI and that person's signals are
> evaluated as usual. The flag marks the **contact**; it does not cancel the analysis.

---

## 2. Precedence

When more than one category applies:

```
INTERESADO  >  RESOLVIO_DUDAS  >  NO_INTERESADO
```

Examples:
- Asked, then stated interest → `INTERESADO`
- Asked, then declined → `RESOLVIO_DUDAS`
- Only declined → `NO_INTERESADO`

### 2.0 Signals are independent of each other

A signal **does not cancel** another: each one is evaluated separately over the whole conversation.
In particular, **a rejection at the end does not erase the information obtained earlier**.

The real case that forced this to be spelled out: the customer asks for `"Efectivo"` (cash), the bot
explains that the credit line does not pay out cash, and the customer answers `"No, gracias"`.

```
busco_informacion  = true   (they did get the clarification)
rechazo_explicito  = true   (they did say no)
categoria_final    = RESOLVIO_DUDAS   (by precedence)
```

The model tended to pick a single signal and drop the other; the prompt now forbids that explicitly.

### 2.1 Individual signals are kept

A single category simplifies reporting but **loses information**: the 112 explicit rejections would
be diluted. So the independent flags are stored as well:

```
interes_declarado    true/false     (initial intent; does NOT define the category)
interes_confirmado   true/false     ← defines INTERESADO
busco_informacion    true/false     ← defines RESOLVIO_DUDAS
rechazo_explicito    true/false
bot_no_resolvio      true/false     (bot quality; does not classify)
es_autorespondedor   true/false     (contact to clean up; does not classify)
categoria_final      <derived from the precedence>
```

This answers questions such as *"how many of the customers who asked ended up declining?"* or *"how
often could the bot not answer?"* without reprocessing anything.

---

## 3. Classification cascade

Order matters: the precedence allows stopping early. Since `INTERESADO` always wins, once a hard rule
detects it **there is no need to find out whether the customer also asked something**, which keeps
those conversations away from the AI.

| Layer | Criterion | Method | Conversations | % of those with a reply |
|---|---|---|---|---|
| 0 | No customer messages | Hard rule | 3,002 | — |
| 1 | `INTERESADO` | Hard rule | 71 | 33% |
| 2 | `NO_INTERESADO` with no other interaction | Hard rule | 69 | 32% |
| 3 | Gray zone | **AI** | 77 | 35% |

**The AI only processes 77 of 3,219 conversations (2.4%).**

### 3.1 Why rules and not AI for layers 0–2

The main argument is **not cost** (at this volume it would be tiny either way) but
**auditability**: a deterministic rule always produces the same result and makes it possible to
explain exactly why a conversation ended up in a given category. The AI is not deterministic and
offers no such guarantee.

The signals used in layers 1 and 2 are reliable because **they do not depend on free text typed by
the customer**:

- **Bot templates**: machine-generated, always the same text.
- **Menu buttons**: the customer *taps* them rather than typing, and they arrive as exact text
  (`No estoy interesado` appears 112 times, character for character).

Running regular expressions over the customer's free text would be brittle: the real sample
contains `"Dodne. Averiguo"`, `"No. Yo voy. Almscen"`, `"Homcenter."` — with typos, no accents and
no punctuation.

---

## 4. Validation

The automatic classification is checked against **blind** manual labelling (the AI's answer is not
shown, so it cannot anchor the human judgement):

```bash
python scripts/validar_ia.py --exportar validacion.xlsx   # export without the AI's answer
# ... fill in the TU_CATEGORIA column ...
python scripts/validar_ia.py --comparar validacion.xlsx   # measure agreement and list disagreements
```

### 4.1 First validation round

The first round gave **60% agreement (30/50)**. Analysing the 20 disagreements was not a formality:
it uncovered four real problems, and every definition marked "revised" or "broadened" in this
document came out of it:

| Cause | Cases | Fix |
|---|---|---|
| `INTERESADO` too broad | 7 | Now requires `interes_confirmado` (taking the credit line, not just stating intent) |
| Business auto-responders | 6 | Rule-based detection + the `es_autorespondedor` flag (§1.5) |
| `SIN_CLASIFICAR` (unclassified) was unnecessary | 5 | Removed; those cases fall into `NO_INTERESADO` |
| `RESOLVIO_DUDAS` too narrow | 2 | Broadened to "obtained information" (§1.3) |

The validation also exposed mistakes of our own:

1. **The prompt counted the bot's questions** as if they were the customer's. Fixed with an explicit
   instruction at the top of the prompt (RULE 1).
2. **The model treated the signals as mutually exclusive**: a rejection at the end erased the
   information obtained earlier. Fixed in §2.0.
3. **The auto-responder rule stopped too early**, assuming that if a business bot replied there was
   no person behind it. Fixed in §1.5.
4. **The model over-flagged `es_autorespondedor`**: it even marked as "business" customers who had
   only tapped *"Quiero usar mi cupo"*, confusing *"the bot is automated"* (it always is — it is the
   company's chatbot) with *"the customer's number belongs to a business"*. After two attempts to
   tune the prompt without reaching good precision, **the signal was removed from the AI
   entirely**: today `es_autorespondedor` is decided by rules only.

   This applies the principle in §3.1: auto-replies are **corporate text with a fixed template**,
   exactly what rules handle well. Asking the model for it was a design mistake. The cost of being
   wrong is also asymmetric — a false positive flags a real customer's number for removal, while a
   false negative just means the conversation is classified normally. So precision is preferred
   over coverage, and the pattern list grows as new formats appear.

   It was caught by auditing the flag itself before reporting it as a business metric, not by an
   automated test: any new signal should be spot-checked before it is trusted.

### 4.2 Second round

With those fixes, 18 of the 20 original disagreements were resolved. The business owner reviewed the
remaining two one by one, and both turned out to be real classifier defects (points 2 and 3 above),
not differences of opinion.

**Lesson on method:** blind validation did not serve to "approve" the classifier; it revealed that
the written definitions did not match the business's actual criteria. It is worth repeating every
time the criteria or the source file change.
