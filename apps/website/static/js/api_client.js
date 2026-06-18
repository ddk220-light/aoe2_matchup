/* api_client.js — shared fetch helpers with timeout + error handling
 *
 * Exposes three globals: apiRequest, apiGet, apiPost.
 * No module system — loaded via <script> in base.html before page scripts.
 */

// Asset catalog: fetch once, expose sprite/icon URL overrides on window so
// constants.js (which loads BEFORE this file) can read them once page scripts run.
// Until it resolves (or in fallback), the resolvers use the static UNIT_SPRITES /
// NAME_TO_ICON maps, so behavior is unchanged.
let _assetCatalogPromise = null;
function loadAssetCatalog() {
  if (!_assetCatalogPromise) {
    _assetCatalogPromise = fetch("/api/assets/catalog")
      .then((r) => (r.ok ? r.json() : null))
      .then((cat) => {
        if (cat) {
          window._ASSET_SPRITES = cat.sprites;
          window._ASSET_ICONS = cat.icons;
          window._ASSET_ANIMS = cat.anims || {};
          window._ASSET_SHEETS = cat.sheets || {};
        }
        return cat;
      })
      .catch(() => null);
  }
  return _assetCatalogPromise;
}
loadAssetCatalog();

var DEFAULT_TIMEOUT_MS = 10000;

function ApiError(message, status, body) {
    this.name = "ApiError";
    this.message = message;
    this.status = status;
    this.body = body;
    if (Error.captureStackTrace) Error.captureStackTrace(this, ApiError);
}
ApiError.prototype = Object.create(Error.prototype);
ApiError.prototype.constructor = ApiError;

async function apiRequest(url, opts) {
    var options = opts || {};
    var method = options.method || "GET";
    var body = options.body != null ? options.body : null;
    var headers = options.headers ? Object.assign({}, options.headers) : {};
    var timeoutMs = options.timeoutMs != null ? options.timeoutMs : DEFAULT_TIMEOUT_MS;
    var externalSignal = options.signal || null;

    var timedOut = false;
    var controller = new AbortController();
    var timeoutId = setTimeout(function () {
        timedOut = true;
        controller.abort();
    }, timeoutMs);

    // If caller passed an external signal, propagate its abort to our controller
    if (externalSignal) {
        if (externalSignal.aborted) {
            controller.abort(externalSignal.reason);
        } else {
            externalSignal.addEventListener("abort", function () {
                controller.abort(externalSignal.reason);
            }, { once: true });
        }
    }

    var init = { method: method, headers: headers, signal: controller.signal };
    if (body != null) {
        init.headers["Content-Type"] = "application/json";
        init.body = JSON.stringify(body);
    }

    var resp;
    try {
        resp = await fetch(url, init);
    } catch (err) {
        clearTimeout(timeoutId);
        if (err.name === "AbortError") {
            if (timedOut) {
                throw new ApiError("Request timed out after " + timeoutMs + "ms", 0, null);
            }
            throw new ApiError("Request to " + url + " aborted", 0, null);
        }
        throw new ApiError("Network error fetching " + url + ": " + err.message, 0, null);
    }
    clearTimeout(timeoutId);

    var text = await resp.text();
    var data = null;
    if (text) {
        try {
            data = JSON.parse(text);
        } catch (e) {
            if (resp.ok) {
                throw new ApiError(
                    "Invalid JSON from " + url,
                    resp.status,
                    text.slice(0, 200)
                );
            }
            // Non-JSON error body — fall through to status check below
        }
    }

    if (!resp.ok) {
        var msg = (data && data.error) || resp.statusText || ("HTTP " + resp.status);
        throw new ApiError(msg, resp.status, data || text);
    }

    if (data && data.error) {
        throw new ApiError(data.error, resp.status, data);
    }

    return data;
}

function apiGet(url, opts) {
    return apiRequest(url, Object.assign({}, opts || {}, { method: "GET" }));
}

function apiPost(url, body, opts) {
    return apiRequest(url, Object.assign({}, opts || {}, { method: "POST", body: body }));
}
