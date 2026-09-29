const path = require("path");
const helper = require("./lib/math");

function run() {
  return path.join("a", "b") + helper.add(1, 2);
}

module.exports = { run };
