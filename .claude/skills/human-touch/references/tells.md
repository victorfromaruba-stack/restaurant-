# What makes a food site look generated

Read this before an audit. Each tell has the reason it reads as fake and what we do
instead. Ordered by how fast a customer notices.

## 1. Pictures (noticed in the first second)

| Tell | Why it reads fake | What we do |
|---|---|---|
| Every dish on the same dark slate, same three-quarter angle, same soft light | One prompt, many dishes. Real kitchens shoot on whatever counter they have | Don't stack big glossy photos; use row thumbnails. Ask for real photos (Menu tile) |
| Steam or smoke curling off everything | Generators add it for "hot". Real phone photos almost never catch steam | Prefer pictures without it on the first screen |
| Props that make no sense: paint streaks or powder swooshes behind tacos, a tortilla-shaped plate, a sauce cup floating | Nobody plates like that in a delivery kitchen | Crop it out, or don't use that picture big |
| Too perfect: symmetrical, glossy, oversaturated, every crumb in place | Real food is a bit messy | A real photo, even an imperfect one, wins |
| Picture doesn't match the words: a thick tall patty on a "smash" burger, four tacos for "(3)", garnish the description doesn't list | Breaks trust the moment the box arrives. Victor's rule: every image shows exactly what its text says | Fix the words to match the truth, or flag the picture in `questions.md` for a real photo. Never "fix" by generating a new near miss |
| The same picture twice on one screen (cover + Featured, restaurant card + dish rail) | The stock-template look: not enough real pictures to go round | One picture, one place. `check.py` catches exact repeats; you catch "two different pictures of the same dish on the same paper" |
| Garbled text on packaging, cans or signs | The surest AI giveaway | Never use a picture with fake lettering. The cans are drawings until real photos exist |
| No packaging anywhere | It's a delivery kitchen: the food arrives in a box or a bag | A real photo of the actual box going out is the most trusted picture we could have. Ask for it |

We are honest that pictures are illustrations ("Pictures are illustrations." on every
page). Keep that line until every picture is a real one.

## 2. Layout and furniture (noticed in the first five seconds)

| Tell | Why | What we do |
|---|---|---|
| A four-point sparkle star (✦) as the logo or decoration | It is the icon of AI products. Customers have learned it means "a bot made this" | A wordmark, or a mark that comes from us (the OPEN sign, the restaurants' own logos) |
| Every section title in giant condensed capitals | Every generated "bold food brand" page does this. When everything shouts, nothing does | One loud thing per screen (page title or the OPEN sign). Section titles in sentence case, smaller |
| Pills on everything: status chips, info chips, filters, options, buttons | The delivery-app template. Chips that can't be tapped pretend to be buttons | Pills only for things you tap. Facts as one plain line: "Open until 2 AM · ƒ5 delivery · 35–50 min" |
| Generic section names: Featured, Popular, Recommended, Signature dishes | Template labels that say nothing about this kitchen | Names that tell the customer what to do or what's there: "Start with these", "Start here", "Family deal" |
| Identical cards in a perfect grid, everything the same radius | Templates repeat; real places have one big thing and smaller things | Vary scale: one hero, then rows. Same radius is fine, same everything isn't |
| Glows, gradients, frosted glass as decoration | Generator defaults | Flat night colours. The OPEN sign may glow because it's a neon sign |
| Fake liveness: "12 people ordering now", countdowns, "only 3 left" | Invented urgency is a lie, and people know the trick | Only real state: open or closed from the hours, sold out from the menu |
| Stock icons everywhere (truck, clock, star) beside every fact | Icon-per-line is template filler | Words. An icon only where it helps a tap (bag, back, search, WhatsApp) |

## 3. Copy (noticed when they read)

| Tell | Why | What we do |
|---|---|---|
| Staccato triads: "Hot. Fresh. Fast." | The single most common generated rhythm | Say it once, plainly: "Cooked to order, delivered in 35–50 min." |
| Every restaurant's tagline in the same shape ("A, B & C") | Stamped from one template | Each restaurant its own sentence, about what's true of it |
| Adjectives instead of facts: delicious, fresh, bold, perfect, mouthwatering | A generator writes them because it knows nothing | Name the ingredient, the cooking, the time: "smashed thin on the flat-top", "with a cup of consommé to dip" |
| Em dashes | Nobody types one in a WhatsApp or on a menu board | Full stop, comma, or two sentences |
| Title Case Buttons And Headings | Template English | Sentence case. Buttons say what happens: "Send on WhatsApp" |
| No contractions: "We are open", "It is ready" | Reads like a form letter | "We're open", "It's ready" |
| "Experience", "journey", "elevate", "crafted", "indulge" | Agency words | Plain verbs: cook, bring, pick, send |
| Invented proof: reviews, ratings, "since 2019", "our chef Maria", "secret family recipe" | Lies, and the first thing a sceptical customer tests | Nothing until Victor confirms it. Then put the exact phrase in `allow.txt` |

## 4. Real signals we already have (use them, don't hide them)

- The WhatsApp number and that orders go to a person on WhatsApp.
- Hours, last orders at 1:30 AM, delivery areas by name, "Elsewhere? Ask us".
- How to pay: cash in florins or US dollars, or bank transfer.
- "House colour helps the driver": that is how addresses work here. Details like this
  are the opposite of generated copy.
- The four languages, and a Papiamento "Danki!" where people would say it.
- The order number and the ticket the chef reads.

## 5. Things only Victor can unlock (ask, one line each, in `questions.md`)

- One real photo of the takeaway box or bag going out.
- Real photos of the dishes, starting with the signatures (the chef app's Menu tile
  saves them straight onto the site, same file path, thumbnails made).
- A photo of the kitchen counter or door (no faces needed).
- One sentence in his own words: why this kitchen exists.
- Permission to quote a real customer's WhatsApp message, with their OK.
- The registered business name and KvK number (a real fact that shows a real business).
