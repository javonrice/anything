import fs from "node:fs";
const words = fs.readFileSync("assets/words.json", "utf8").trim();
fs.writeFileSync("index.html", fs.readFileSync("index.src", "utf8").replace("__WORDS__", words));
