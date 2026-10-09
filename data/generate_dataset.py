import csv
import random

random.seed(42)

products = [
    "wireless earbuds", "coffee maker", "running shoes", "laptop backpack",
    "yoga mat", "bluetooth speaker", "kitchen blender", "office chair",
    "phone case", "air fryer", "gaming mouse", "winter jacket",
    "skincare serum", "water bottle", "desk lamp", "electric toothbrush",
    "board game", "children's toy", "hiking boots", "wall clock",
]

genuine_templates = [
    "I've been using this {p} for about {n} weeks now and overall I'm happy with it. The build quality feels solid, though the {flaw} could be better. Would recommend if you're not too picky.",
    "Bought this {p} for my {person} last month. It works well for everyday use but the {flaw} was a bit disappointing given the price. Still, three out of five stars from me.",
    "Honestly mixed feelings about this {p}. The first few days it worked great, but after {n} weeks I noticed the {flaw}. Customer service was responsive when I reached out though.",
    "This {p} does exactly what it says on the box. Not amazing, not terrible. Delivery took {n} days which was slower than expected, but the packaging was good.",
    "I compared this {p} with two other brands before buying. It's a bit more expensive but the {feature} makes up for it. The {flaw} is the only downside I've found so far.",
    "Used this {p} daily for {n} months. Started developing minor issues with the {flaw}, so I contacted support and they were helpful. Overall decent value for the price.",
    "My {person} recommended this {p} and after {n} weeks of use I can say it's pretty good. Not perfect, the {flaw} bugs me sometimes, but I'd probably buy it again.",
    "Picked this up during a sale. The {feature} is genuinely useful day to day. Setup took longer than the manual suggested and the {flaw} needs improvement.",
    "Works as described. I had one minor issue with the {flaw} in the first week but it resolved itself. The {feature} is the best part honestly.",
    "Three stars. It's fine for the price but don't expect anything special. The {feature} works, the {flaw} doesn't, pretty standard for this price range.",
]

fake_templates = [
    "BEST {P} EVER!!! Changed my life completely!!! 5 stars!!! Everyone needs to buy this RIGHT NOW!!! Amazing amazing amazing!!!",
    "This {p} is absolutely perfect in every single way!!! No flaws at all!!! Best purchase of my entire life!!! Highly highly recommend!!!",
    "WOW just WOW! This {p} exceeded all my expectations!!! 10/10 would buy again and again!!! Amazing quality amazing price amazing everything!!!",
    "I received this {p} for free in exchange for my honest review and I have to say it is INCREDIBLE!!! Five stars all the way!!! Buy it now!!!",
    "Perfect perfect perfect!!! This {p} is the greatest product I have ever owned in my whole life!!! Everyone should buy this immediately!!!",
    "Amazing product!!! Fast shipping!!! Great seller!!! Best {p} on the market!!! I am so so happy!!! Will definitely buy again!!! 100 stars if I could!!!",
    "This {p} literally cured all my problems overnight! Unbelievable results! Best decision I've ever made! Buy buy buy!!!",
    "Outstanding!!! Incredible!!! Life changing!!! This {p} is simply the best thing money can buy!!! Don't even think just buy it now!!!",
    "5 STARS!!! This {p} is a total game changer!!! Super fast super amazing super perfect!!! Everybody needs one of these!!!",
    "I am blown away by this {p}!!! Absolutely no complaints whatsoever!!! Perfect in every way!!! Highly highly highly recommend to everyone!!!",
]

flaws = ["battery life", "stitching", "packaging", "instructions", "noise level",
         "plastic casing", "charging cable", "zipper", "screen brightness", "grip"]
features = ["battery life", "design", "comfort", "sound quality", "build quality",
            "portability", "warranty", "grip", "material", "speed"]
persons = ["sister", "brother", "wife", "husband", "friend", "coworker", "mom", "dad"]


def make_genuine(n_rows):
    rows = []
    for _ in range(n_rows):
        t = random.choice(genuine_templates)
        p = random.choice(products)
        text = t.format(
            p=p,
            n=random.randint(2, 12),
            flaw=random.choice(flaws),
            feature=random.choice(features),
            person=random.choice(persons),
        )
        rows.append((text, 0))
    return rows


def make_fake(n_rows):
    rows = []
    for _ in range(n_rows):
        t = random.choice(fake_templates)
        p = random.choice(products)
        text = t.format(p=p, P=p.upper())
        rows.append((text, 1))
    return rows


def main():
    rows = make_genuine(300) + make_fake(300)
    random.shuffle(rows)
    with open("reviews_dataset.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["review_text", "label"])
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows to reviews_dataset.csv")


if __name__ == "__main__":
    main()
