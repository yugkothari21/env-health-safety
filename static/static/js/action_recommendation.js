/**
 * Action Recommendation Panel
 * ---------------------------
 * Reads values already present on the page
 * Does NOT change backend or calculations
 */

function updateActionRecommendation(
  noiseLevel,
  exposureTime,
  oxygenLevel,
  airQualityIndex
) {
  let status = "SAFE";
  let primaryAction = "No immediate action required.";
  let secondaryAction = "Environment conditions are within safe limits.";

  // ---- NOISE LOGIC ----
  if (noiseLevel >= 90) {
    status = "DANGER";
    primaryAction = "Leave the noisy area immediately.";
    secondaryAction = "Use ear protection if exposure continues.";
  } else if (noiseLevel >= 75 && exposureTime >= 30) {
    status = "CAUTION";
    primaryAction = "Reduce noise exposure.";
    secondaryAction = "Take a 10–15 minute break in a quieter area.";
  }

  // ---- OXYGEN LOGIC ----
  if (oxygenLevel !== null && oxygenLevel <= 16) {
    status = "DANGER";
    primaryAction = "Descend to a lower altitude immediately.";
    secondaryAction = "Seek medical help if symptoms appear.";
  } else if (oxygenLevel !== null && oxygenLevel <= 19) {
    status = "CAUTION";
    primaryAction = "Avoid physical exertion.";
    secondaryAction = "Monitor oxygen levels closely.";
  }

  // ---- AIR QUALITY LOGIC ----
  if (airQualityIndex !== null && airQualityIndex >= 300) {
    status = "DANGER";
    primaryAction = "Avoid outdoor exposure.";
    secondaryAction = "Wear a protective mask if unavoidable.";
  } else if (airQualityIndex !== null && airQualityIndex >= 150) {
    status = "CAUTION";
    primaryAction = "Limit prolonged outdoor activity.";
    secondaryAction = "Sensitive individuals should stay indoors.";
  }

  // ---- UPDATE UI ----
  const panel = document.getElementById("action-recommendation-panel");
  const statusEl = document.getElementById("action-status");

  if (!panel || !statusEl) return;

  document.getElementById("primary-action").innerText = primaryAction;
  document.getElementById("secondary-action").innerText = secondaryAction;

  statusEl.innerText = `Status: ${status}`;
  statusEl.className = "";

  panel.style.borderLeftColor =
    status === "SAFE" ? "#2ecc71" :
    status === "CAUTION" ? "#f1c40f" :
    "#e74c3c";

  statusEl.classList.add(status.toLowerCase());
}
