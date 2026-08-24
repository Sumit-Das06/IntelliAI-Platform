"""The console shell: served, navigable, invisible to the API contract.

The console is pages, not APIs — it must render the platform shell,
serve its shared assets with honest content types, keep the OpenAPI
schema untouched, and obey the public product rule: customers see
IntelliAI services, never foundation-model names.
"""

from importlib.resources import files

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from intelliai_api.core.config import Settings
from tests.helpers import client_with_db

pytestmark = pytest.mark.anyio


async def test_the_home_page_is_served_as_html(settings: Settings, db_engine: AsyncEngine) -> None:
    async with client_with_db(settings, db_engine) as (client, _factory):
        response = await client.get("/console/home")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert 'data-page="home"' in response.text
    assert "Welcome to IntelliAI Platform" in response.text
    assert "One API for Speech Intelligence today." in response.text
    # Recent Activity ships as an HONEST empty state until real data
    # wires in — no invented backend, no fake rows.
    assert "Recent Activity" in response.text
    assert "No activity yet" in response.text


async def test_the_keys_page_is_served_as_html(settings: Settings, db_engine: AsyncEngine) -> None:
    async with client_with_db(settings, db_engine) as (client, _factory):
        response = await client.get("/console/keys")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert 'data-page="keys"' in response.text
    assert "Manage API keys for accessing IntelliAI AI Services." in response.text
    # The page carries its own empty state and the shown-once warning:
    # both are product promises, not decoration.
    assert "No API Keys Yet" in response.text
    assert "it will never be shown again" in response.text


async def test_the_services_page_is_served_as_html(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    async with client_with_db(settings, db_engine) as (client, _factory):
        response = await client.get("/console/services")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert 'data-page="services"' in response.text
    assert "The IntelliAI product catalogue" in response.text


async def test_the_catalogue_speaks_in_products_and_languages(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    # The catalogue data lives in the shared console kit: categories are
    # product truths (Speech, Document Intelligence, ...), languages carry
    # honest tiers (Hindi and Arabic are beta), and every future service
    # is one entry — this test pins the vocabulary customers see.
    async with client_with_db(settings, db_engine) as (client, _factory):
        js = (await client.get("/console/assets/console.js")).text

    for category in (
        "Speech",
        "Speech Synthesis",
        "Document Intelligence",
        "Translation",
        "Vision",
        "LLM",
    ):
        assert category in js
    assert '{ name: "English", tier: "production" }' in js
    assert '{ name: "Hindi", tier: "beta" }' in js
    assert '{ name: "Arabic", tier: "beta" }' in js


async def test_the_samples_page_is_served_as_html(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    async with client_with_db(settings, db_engine) as (client, _factory):
        response = await client.get("/console/samples")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert 'data-page="samples"' in response.text
    assert "Speech Samples" in response.text
    # The data page carries the permanent consent notice and honest
    # empty/lifecycle vocabulary.
    assert "Recordings, transcripts, and submitted corrections may be stored" in response.text
    assert "No speech samples yet" in response.text
    assert "Lifecycle" in response.text


async def test_the_datasets_page_is_served_as_html(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    async with client_with_db(settings, db_engine) as (client, _factory):
        response = await client.get("/console/datasets")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert 'data-page="datasets"' in response.text
    # Honest empty state with a way forward, and the product's purpose
    # stated in product words — future IntelliAI STT fine-tuning.
    assert "No datasets yet" in response.text
    assert "future IntelliAI STT fine-tuning" in response.text
    # The immutability promise is a product promise, not decoration: it
    # must appear wherever a version can be created.
    assert (
        "immutable snapshot of the currently eligible samples. "
        "Future corrections or new samples will not change this version."
    ) in response.text
    # The page reads ONLY the dataset APIs and the preview it renders is
    # the server's answer — never a client-side recount.
    assert "/v1/datasets" in response.text
    assert "/preview" in response.text
    # Latest-request-wins guards the drawer's async fills.
    assert "var ticket = ++drawerTicket;" in response.text
    assert "if (ticket !== drawerTicket) return;" in response.text


async def test_the_datasets_page_prepares_training_data(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    # Commit 12: every version card carries its Training Data verdict.
    async with client_with_db(settings, db_engine) as (client, _factory):
        page = (await client.get("/console/datasets")).text

    # The three honest states, in product words.
    assert "Not prepared yet" in page
    assert "Prepare Training Data" in page
    assert "✓ Ready" in page
    assert "Ready for future IntelliAI STT fine-tuning." in page
    assert "⚠ Validation failed" in page
    assert "no manifest was created." in page
    assert "Retry Preparation" in page
    # Failure reasons are named for humans, from the machine vocabulary.
    for reason in (
        "audio file unavailable",
        "missing transcript",
        "missing language",
        "samples were erased after this version froze",
    ):
        assert reason in page
    # The verdict comes from the preparation API — never a client recount.
    assert '"/preparation"' in page
    assert '"/prepare"' in page
    # The next action is intentionally absent: preparation is where this
    # milestone ends.
    for absent in ("Train Model", "Fine-tune", "Deploy"):
        assert absent not in page


async def test_the_usage_page_is_served_as_html(settings: Settings, db_engine: AsyncEngine) -> None:
    async with client_with_db(settings, db_engine) as (client, _factory):
        response = await client.get("/console/usage")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert 'data-page="usage"' in response.text
    # The four stat cards, named exactly as the product names them.
    for card in (
        "API Requests",
        "Speech Minutes",
        "Average Request Duration",
        "Platform Success Rate",
    ):
        assert card in response.text
    # Success rate must state what it measures AND what it excludes.
    assert "Accepted requests completed by IntelliAI STT" in response.text
    assert "rejected as invalid before processing are excluded" in response.text
    # Services, not models: the public product identity.
    assert "Services Used" in response.text
    assert "IntelliAI STT" in response.text
    # Honest empty state with a way forward.
    assert "No API usage yet" in response.text
    assert "Open STT Studio" in response.text


async def test_usage_offers_the_three_granularities(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    # Granularity is a control of its own, independent of the period.
    async with client_with_db(settings, db_engine) as (client, _factory):
        page = (await client.get("/console/usage")).text

    for granularity in ("daily", "hourly", "minute"):
        assert f'data-granularity="{granularity}"' in page
    assert 'data-granularity="daily" aria-pressed="true"' in page  # the default
    assert 'aria-label="Granularity"' in page


async def test_usage_asks_the_api_by_range_and_granularity(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    # Every selection re-asks the API with start/end/granularity — the
    # window is the server's decision, never a client-side reslice, and
    # the retired days-only flow is gone from the new UI.
    async with client_with_db(settings, db_engine) as (client, _factory):
        page = (await client.get("/console/usage")).text

    assert '"?start=" + state.start + "&end=" + state.end +' in page
    assert '"&granularity=" + state.granularity' in page
    assert '"/v1/usage/summary" + query' in page
    # The compatibility field of the old contract is not the new source.
    assert "body.daily" not in page
    assert "renderTrend(body.series)" in page
    # Latest-request-wins survives the upgrade.
    assert "var ticket = ++requestSeq;" in page
    assert "if (ticket !== requestSeq) return;" in page


async def test_usage_offers_every_range_shortcut(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    async with client_with_db(settings, db_engine) as (client, _factory):
        page = (await client.get("/console/usage")).text

    for shortcut in (
        '{ label: "Today", days: 1 }',
        '{ label: "Last 7 Days", days: 7 }',
        '{ label: "Last 14 Days", days: 14 }',
        '{ label: "Last 30 Days", days: 30 }',
        '{ label: "Last 60 Days", days: 60 }',
        '{ label: "Last 90 Days", days: 90 }',
    ):
        assert shortcut in page
    # A custom range is picked on a real calendar, with Cancel/Apply.
    assert 'id="picker-cancel"' in page
    assert 'id="picker-apply"' in page
    assert 'id="months"' in page
    assert 'role: "gridcell"' in page  # day cells are built by the page's own JS


async def test_usage_guides_instead_of_sending_impossible_requests(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    # The backend's ceilings, restated in the UI's own words, applied
    # before a request is made — and never by silently rewriting the
    # user's selection.
    async with client_with_db(settings, db_engine) as (client, _factory):
        page = (await client.get("/console/usage")).text

    assert "Daily view supports ranges up to 90 days." in page
    assert "Hourly view supports ranges up to 30 days." in page
    assert "Minute view supports ranges up to 48 hours." in page
    # Incompatible shortcuts are unavailable rather than broken, and a
    # too-long custom range cannot be applied.
    assert "button.disabled = true;" in page
    # Apply is refused both for an impossible range and for a range whose
    # end has not been chosen yet.
    assert 'document.getElementById("picker-apply").disabled = pending || tooLong;' in page
    assert "note.textContent = pending" in page
    assert '"Select an end date."' in page
    # An impossible selection stops before the network call.
    assert "if (exceeds(state.start, state.end, state.granularity)) {" in page


async def test_usage_never_shows_stale_numbers_for_a_new_selection(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    # A pending request dims what it is replacing; a failed one replaces
    # the numbers with an error rather than leaving the previous
    # period's figures under the new selection.
    async with client_with_db(settings, db_engine) as (client, _factory):
        page = (await client.get("/console/usage")).text

    assert 'analytics.classList.add("is-loading");' in page
    assert 'analytics.classList.remove("is-loading");' in page
    assert "Usage could not be loaded" in page
    assert 'id="retry"' in page


async def test_usage_keeps_the_chart_reachable_without_a_mouse(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    # Per-bucket detail must not be mouse-only: one focus stop drives a
    # cursor across every bucket, with the value written out in text.
    async with client_with_db(settings, db_engine) as (client, _factory):
        page = (await client.get("/console/usage")).text

    assert 'tabindex: "0"' in page
    assert 'chart.addEventListener("keydown"' in page
    assert "ArrowLeft: -1, ArrowRight: 1" in page
    assert 'id="chart-readout"' in page
    # The picker is keyboard-navigable and Escape closes it.
    assert 'picker.addEventListener("keydown"' in page
    assert 'if (event.key === "Escape" && !picker.classList.contains("hidden"))' in page


async def test_usage_never_rounds_into_a_perfect_or_empty_record(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    # A window containing failures must never print 100%, and a window
    # containing successes must never print 0% — rounding may not cross
    # either boundary. The same honesty the API applies to null rates.
    async with client_with_db(settings, db_engine) as (client, _factory):
        page = (await client.get("/console/usage")).text

    assert 'if (rate < 1 && text === "100.0") text = "99.9";' in page
    assert 'if (rate > 0 && text === "0.0") return "<0.1%";' in page


async def test_usage_distinguishes_a_quiet_window_from_a_new_account(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    # "No API usage yet" is a claim about the ACCOUNT. Telling an
    # established customer that during a quiet week would be false, so
    # the page only says it when the widest window is empty too.
    async with client_with_db(settings, db_engine) as (client, _factory):
        page = (await client.get("/console/usage")).text

    assert "No API usage in this period" in page
    assert "Your organization has usage outside " in page
    # The widest window it can ask about, in the new contract's terms.
    assert "var widest = shortcutRange(90);" in page
    assert '"/v1/usage/summary?start=" + widest.start + "&end=" + widest.end' in page


async def test_usage_dates_are_formatted_in_the_platform_s_own_utc_days(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    # The API counts UTC calendar days. Rendering them in local time
    # would move every label west of Greenwich to the previous day, so
    # the formatter is pinned to UTC.
    async with client_with_db(settings, db_engine) as (client, _factory):
        page = (await client.get("/console/usage")).text

    assert 'timeZone: "UTC"' in page
    assert 'return new Date(iso + "T00:00:00Z");' in page
    assert "function todayISO() { return new Date().toISOString().slice(0, 10); }" in page
    # Hourly and minute axes read as clock times, and say which clock.
    assert '{ hour: "numeric", timeZone: "UTC" }' in page
    assert 'hour: "2-digit", minute: "2-digit", hour12: false, timeZone: "UTC"' in page
    assert "times in UTC" in page


async def test_usage_names_services_from_the_catalogue(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    # Public product names come from the shared registry, so a service
    # launched later is named correctly without editing this page — and
    # a raw model id is never shown as a product name.
    async with client_with_db(settings, db_engine) as (client, _factory):
        page = (await client.get("/console/usage")).text
        js = (await client.get("/console/assets/console.js")).text

    assert "IntelliAI.serviceName(entry.key)" in page
    assert 'id = String(publicModelId).replace(/^intelliai-/, "")' in js


async def test_usage_reads_only_the_usage_api(settings: Settings, db_engine: AsyncEngine) -> None:
    # The separation law from Commit 7, enforced on the page as well:
    # Usage never derives its numbers from the dataset APIs.
    async with client_with_db(settings, db_engine) as (client, _factory):
        page = (await client.get("/console/usage")).text

    assert "/v1/usage/summary" in page
    assert "/v1/speech-samples" not in page
    for dataset_word in ("Corrections", "Storage Used", "Dataset", "Consent"):
        assert dataset_word not in page


async def test_every_front_door_leads_to_home(settings: Settings, db_engine: AsyncEngine) -> None:
    # A platform whose front door 404s is not a platform — and both
    # roots land on Home, the page that answers "what should I do first?"
    async with client_with_db(settings, db_engine) as (client, _factory):
        root = await client.get("/")
        console = await client.get("/console")

    assert root.status_code == 307
    assert root.headers["location"] == "/console/home"
    assert console.status_code == 307
    assert console.headers["location"] == "/console/home"


async def test_the_shared_assets_are_served_with_their_types(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    async with client_with_db(settings, db_engine) as (client, _factory):
        css = await client.get("/console/assets/console.css")
        js = await client.get("/console/assets/console.js")

    assert css.status_code == 200
    assert css.headers["content-type"].startswith("text/css")
    assert "--accent" in css.text  # the design tokens live here
    assert js.status_code == 200
    assert js.headers["content-type"].startswith("text/javascript")
    assert "IntelliAI" in js.text


async def test_an_unknown_asset_is_a_plain_404(settings: Settings, db_engine: AsyncEngine) -> None:
    # The allowlist is the whole route: no directory semantics, no
    # traversal surface, no error event for a mistyped filename.
    async with client_with_db(settings, db_engine) as (client, _factory):
        response = await client.get("/console/assets/secrets.txt")

    assert response.status_code == 404


async def test_the_navigation_carries_the_whole_platform(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    # The IA ships complete on day one: live pages link, future pages
    # show as Soon — adding a service is one NAV entry, nothing else.
    async with client_with_db(settings, db_engine) as (client, _factory):
        js = (await client.get("/console/assets/console.js")).text

    for label in (
        "Home",
        "API Keys",
        "Playground",
        "Speech Studio",
        "AI Services",
        "Speech Samples",
        "Datasets",
        "Usage",
        "Logs",
        "Settings",
        "Billing",
    ):
        assert label in js
    for service in (
        "IntelliAI STT",
        "IntelliAI TTS",
        "IntelliAI OCR",
        "IntelliAI Translate",
        "IntelliAI Vision",
        "IntelliAI LLM",
    ):
        assert service in js
    # Pages that have shipped must be LIVE in the registry — reverting a
    # flip would silently unlink a working page from the whole console.
    for live_entry in (
        '{ id: "home", label: "Home", href: "/console/home", status: "live" }',
        '{ id: "keys", label: "API Keys", href: "/console/keys", status: "live" }',
        '{ id: "playground", label: "Playground", href: "/console/playground", status: "live" }',
        '{ id: "speech", label: "Speech Studio", href: "/console/speech", status: "live" }',
        '{ id: "services", label: "AI Services", href: "/console/services", status: "live" }',
        '{ id: "samples", label: "Speech Samples", href: "/console/samples", status: "live" }',
        '{ id: "datasets", label: "Datasets", href: "/console/datasets", status: "live" }',
        '{ id: "usage", label: "Usage", href: "/console/usage", status: "live" }',
    ):
        assert live_entry in js


async def test_the_public_product_rule_holds(settings: Settings, db_engine: AsyncEngine) -> None:
    # Customers see IntelliAI STT. Foundation models are an
    # implementation detail and never appear in the console.
    async with client_with_db(settings, db_engine) as (client, _factory):
        pages = [
            (await client.get("/console/home")).text,
            (await client.get("/console/keys")).text,
            (await client.get("/console/services")).text,
            (await client.get("/console/samples")).text,
            (await client.get("/console/datasets")).text,
            (await client.get("/console/usage")).text,
            (await client.get("/console/playground")).text,
            (await client.get("/console/speech")).text,
            (await client.get("/console/assets/console.js")).text,
            (await client.get("/console/assets/console.css")).text,
        ]

    for text in pages:
        assert "whisper" not in text.lower()
        # Post-M26 the Hindi route runs the in-house specialist; its
        # vocabulary must be as invisible as the incumbent's.
        assert "qwen" not in text.lower()
        assert "llama" not in text.lower()
        assert "gguf" not in text.lower()
        # M35: the synthesis engine and its phonemizer are equally
        # internal - no console surface may ever name them.
        assert "kokoro" not in text.lower()
        assert "espeak" not in text.lower()
        assert "af_heart" not in text.lower()
        assert "am_michael" not in text.lower()
        # Dashboard was renamed to Home in Commit 6; the old word must
        # never resurface on any console surface.
        assert "dashboard" not in text.lower()


async def test_the_openapi_schema_is_unchanged(settings: Settings, db_engine: AsyncEngine) -> None:
    async with client_with_db(settings, db_engine) as (client, _factory):
        schema = (await client.get("/openapi.json")).json()

    # Pages, not APIs: nothing under /console enters the contract.
    assert not any(path.startswith("/console") for path in schema["paths"])
    assert "/" not in schema["paths"]


def test_the_console_assets_ship_inside_the_package() -> None:
    # importlib.resources is how the routes read them, so this is exactly
    # the packaging guarantee: wherever the package goes, the console goes.
    console = files("intelliai_api") / "static" / "console"
    for name in (
        "home.html",
        "keys.html",
        "services.html",
        "studio.html",
        "speech.html",
        "samples.html",
        "datasets.html",
        "usage.html",
        "console.css",
        "console.js",
    ):
        asset = console / name
        assert asset.is_file()


async def test_badge_semantics_are_documented_and_rendered_as_designed(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    # M31: "Production" on a service card means LAUNCHED AS A PRODUCT
    # (its opposite is "Coming Soon") — never "currently deployed on
    # production infrastructure". The semantics live as a comment at the
    # data source and as the ternary in both renderers; this pin keeps
    # all three from drifting apart or being silently reinterpreted.
    async with client_with_db(settings, db_engine) as (client, _factory):
        js = (await client.get("/console/assets/console.js")).text
        services = (await client.get("/console/services")).text
    assert "BADGE SEMANTICS" in js
    assert "NOT a claim about which infrastructure" in js
    for surface in (js, services):
        assert 'live ? "Production" : "Coming Soon"' in surface


async def test_the_playground_documents_the_audio_ceiling(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    async with client_with_db(settings, db_engine) as (client, _factory):
        studio = (await client.get("/console/playground")).text
    assert "Up to 10 minutes" in studio
    assert "never cut short" in studio


async def test_the_speech_studio_is_a_real_tts_client(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    # M35: the first actual Web TTS experience. The page must carry the
    # product vocabulary (public voices, the documented ceiling, every
    # UX state's plumbing) and none of the engine vocabulary — the
    # public-product sweep above already proves the negative half.
    async with client_with_db(settings, db_engine) as (client, _factory):
        response = await client.get("/console/speech")
    assert response.status_code == 200
    page = response.text
    assert "Speech Studio" in page
    assert 'value="english-female"' in page and 'value="english-male"' in page
    assert "English Female" in page and "English Male" in page
    assert "Up to 2000 characters" in page and "never cut short" in page
    assert '"/v1/audio/speech"' in page  # the EXISTING public contract, no new endpoint
    assert "intelliai-tts" in page
    assert "<audio" in page and "Download WAV" in page
    # Every failure state has friendly words - never a spinner forever.
    for phrase in (
        "Connect your API key",
        "temporarily unavailable",
        "too quickly",
        "2000-character limit",
    ):
        assert phrase in page
    # M36: progressive playback is the page's default path - stream mode
    # requested, gapless AudioContext scheduling, and a whole-body
    # fallback for browsers without the APIs.
    assert "stream: true" in page
    assert "stream: false" in page  # the fallback path stays whole-body
    assert "AudioContext" in page
    assert "generateWholeBody" in page
    # M37: ONE playback session, ONE audible source - the state machine,
    # the stale-session guard, and the structural guarantees that the
    # replay element can never sound while the live context exists.
    for state in ("GENERATING", "STREAMING", "PAUSED", "COMPLETED", "STOPPED", "ERROR"):
        assert '"' + state + '"' in page
    for word in ("Playing…", "Paused.", "Completed.", "Stopped.", "first audio"):
        assert word in page
    assert "activeSessionId" in page and "isStale" in page  # session identity
    assert 'playerWrap.classList.toggle("hidden", state !== "COMPLETED")' in page
    assert "__iaiPlayback" in page and "audibleSources" in page  # observable proof
    assert "ctx.suspend()" in page and "ctx.resume()" in page  # pause/resume, same session
    # Completion order law: the live context is torn down BEFORE the
    # replay src is attached - the two mechanisms never overlap.
    completed_block = page[
        page.index("function completeSession") : page.index('transition(session, "COMPLETED")')
    ]
    assert "teardown(session)" in completed_block
    assert completed_block.index("teardown(session)") < completed_block.index("player.src")
    # M39: the dropdown mirrors the DEPLOYMENT's catalog — friendly
    # Hindi names exist in the rebuild table, the list rebuilds from
    # the public voices endpoint (staging lists Hindi, production does
    # not), and the served-page STATIC baseline stays English-only.
    assert '"/v1/audio/voices"' in page
    assert '"hindi-female"' in page and "Hindi Female" in page
    assert '"hindi-male"' in page and "Hindi Male" in page
    assert "rebuildVoices" in page
    assert 'value="hindi-female"' not in page  # options arrive from the catalog, never hardcoded
    # Hindi text example rides the voice switch; engine tokens never appear.
    assert "नमस्ते" in page
    for banned in ("hf_alpha", "hm_psi", "af_heart", "am_michael"):
        assert banned not in page


async def test_the_services_card_links_the_speech_studio_without_claiming_launch(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    # The badge is a LAUNCH claim and TTS has not launched: the card
    # stays "Coming Soon" while linking the working preview. A link is
    # page availability; a badge is product state - documented at the
    # data source and pinned here.
    async with client_with_db(settings, db_engine) as (client, _factory):
        js = (await client.get("/console/assets/console.js")).text
    assert '"/console/speech"' in js
    assert "Open Speech Studio" in js
    assert "no promise yet" in js  # the documented soon+href semantics
