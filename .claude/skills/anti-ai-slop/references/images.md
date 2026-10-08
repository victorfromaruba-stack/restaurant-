# Pictures

Pictures are judged before a single word is read. A generated picture that's slightly
wrong costs more trust than no picture.

## Generated-photo tells (check every picture, at full size)

- The same background, angle and soft light on every item: one prompt, many products.
- Steam or smoke on everything, glossy sheen, oversaturated colour, perfect symmetry.
- Props that make no sense: paint streaks or powder swooshes behind food, objects
  floating, plates shaped like the food, a drink with no glass.
- Text that's almost text: garbled letters on signs, cans, menus, boats, shirts.
- Hands, fingers, faces, teeth, reflections and water that don't quite work.
- The picture doesn't match the words: a thick patty on a "smash" burger, four tacos for
  "(3)", a speedboat for "catamaran", a beach that isn't the one named, garnish the
  description doesn't list.
- The same picture used twice on one page, or two near-identical pictures of the same thing.

`slop_check.py` catches exact and near-exact repeats on a page and generator-style file
names. The rest needs eyes.

## What to do

1. **Label honestly** while pictures are illustrations ("Pictures are illustrations.").
2. **One picture, one place.** Don't repeat a photo to fill a card.
3. **Match the words.** If the picture and the description disagree, fix the words to the
   truth, or swap the picture. Never generate a new near miss.
4. **Push for real photos.** A phone photo of the real thing (the actual box going out, the
   actual boat at the actual dock) beats a perfect render. Make it easy for the owner:
   say exactly which shot, from which angle, in what light ("the burger in its box on the
   counter, from above, by the window, no flash").
5. **When generating is the only option** (and the owner said yes to the cost): describe
   the real thing exactly as it's served or seen, real packaging, natural light, a
   plain real surface, nothing the description doesn't list, no text in the picture.
   Then look at every result at full size against the words before using it.
