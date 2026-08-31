# Price / Volume / Mix Waterfall

Part of the [fin-telligent](https://github.com/yixuan116/fin-telligent) series.

AI-driven financial diagnostics in a few minutes. A single-page, chat-style demo that opens
on a gross profit miss (down 15% despite flat revenue), traces it to a product mix shift
with a price times volume breakdown, then walks through three fix options: one ruled out
live, and two priced out with waterfall charts, including an interactive breakeven price
slider. One turn at a time, styled like a live conversation with an AI assistant.

Pure HTML, CSS, and JavaScript. No build step, no frameworks. Charts via [Chart.js](https://www.chartjs.org/).

**Live demo:** [yixuan116.github.io/fin-telligent/price-volume-mix-waterfall/](https://yixuan116.github.io/fin-telligent/price-volume-mix-waterfall/)

**Video walkthrough:** [youtube.com/watch?v=eXZR-pW_UO4](https://www.youtube.com/watch?v=eXZR-pW_UO4)

## Screenshots

The conversation unfolds one question at a time. Each screenshot below is the page state
after that step, expanded down through the prior ones.

**Page 1, the snapshot loads automatically**

![Page 1](screenshots/page-1.png)

**Page 2, per-unit profit by product line**

![Page 2](screenshots/page-2.png)

**Page 3, Q1 versus Q2 mix shift**

![Page 3](screenshots/page-3.png)

**Page 4, price times volume drivers**

![Page 4](screenshots/page-4.png)

**Page 5, three options, Raise Price ruled out on click**

![Page 5](screenshots/page-5.png)

**Page 6, Option B: promotional pricing, with an interactive breakeven price slider**

![Page 6](screenshots/page-6.png)

**Page 7, Option C: change sales commission**

![Page 7](screenshots/page-7.png)

**Page 8, wrap up and contact**

![Page 8](screenshots/page-8.png)

## Structure

```
fin-telligent/
  price-volume-mix-waterfall/
    index.html        the complete demo, one file
    Pictures/          QR code images used on the contact section
    screenshots/
    README.md
```

## Running locally

Open `price-volume-mix-waterfall/index.html` directly in a browser, or serve the folder:

```
cd price-volume-mix-waterfall
python3 -m http.server 8000
```

Then visit `http://localhost:8000`.

## Contact

Yixuan Jing, [github.com/yixuan116](https://github.com/yixuan116)
