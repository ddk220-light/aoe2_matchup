// Pure deep-link parser for the Battle Sim. Works in the browser and node.
(function (root) {
  function readSimParams(search) {
    const q = new URLSearchParams(search || "");
    const get = (k) => (q.has(k) ? q.get(k) : null);
    return {
      civ1: get("civ1"), unit1: get("unit1"),
      civ2: get("civ2"), unit2: get("unit2"),
      age1: get("age1"), age2: get("age2"),
      mode: get("mode"),
      resources: get("resources"),
      count1: get("count1"), count2: get("count2"),
      autorun: q.get("autorun") === "1",
    };
  }
  if (typeof module !== "undefined" && module.exports) {
    module.exports = { readSimParams };
  } else {
    root.readSimParams = readSimParams;
  }
})(typeof window !== "undefined" ? window : this);
