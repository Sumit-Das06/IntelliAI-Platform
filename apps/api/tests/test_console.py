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
    # M41: the binary ternary became the shared three-state model —
    # badgeFor() is the ONE place badge text is decided, and both
    # renderers consume it (no page invents its own badge wording).
    assert 'return { text: "Production", cls: "badge-live" }' in js
    assert 'return { text: "Preview", cls: "badge-beta" }' in js
    assert 'return { text: "Coming Soon", cls: "badge-soon" }' in js
    assert "IntelliAI.badgeFor" in services


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
    # The Speech Studio mirrors the Playground's developer surface:
    # a collapsed Developer details block and a copyable "Use it from
    # code" section calling the SAME public endpoint this page calls.
    assert '<details class="dev-details"' in page
    assert "<summary>Developer details</summary>" in page
    assert "Use it from code" in page
    assert 'data-example="curl"' in page and 'data-example="python"' in page
    assert 'data-copy-target="example-curl"' in page
    assert "IntelliAI.speechExamples" in page
    # The launch badge is catalog-driven here too - no hardcoded word.
    assert 'id="tts-status-badge"' in page
    assert "IntelliAI TTS · Preview" not in page
    assert "IntelliAI TTS · Production" not in page
    assert "IntelliAI.withStatus" in page and "IntelliAI.badgeFor" in page
    # Hindi text example rides the voice switch; engine tokens never appear.
    assert "नमस्ते" in page
    for banned in ("hf_alpha", "hm_psi", "af_heart", "am_michael"):
        assert banned not in page


async def test_the_services_card_links_the_speech_studio_without_claiming_launch(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    # The badge is a LAUNCH claim and TTS has not launched in
    # production: the STATIC catalogue entry stays "soon" (the
    # production-safe default) while linking the working preview.
    # M41 upgrades it to Preview at RENDER time, only where the
    # deployment's own /console/status says so.
    async with client_with_db(settings, db_engine) as (client, _factory):
        js = (await client.get("/console/assets/console.js")).text
    assert '"/console/speech"' in js
    assert "Open Speech Studio" in js
    assert 'status: "soon"' in js  # the static tts default, never "preview"
    assert "PRODUCTION-SAFE" in js  # the documented M41 semantics
    assert "withStatus" in js and "badgeFor" in js
    assert '"/console/status"' in js  # status comes from the deployment, not the file
    assert '"Preview"' in js and '"Coming Soon"' in js and '"Production"' in js


class TestLaunchStatus:
    """ONE badge meaning for every service (the M31 law): "production"
    says the service is LAUNCHED as a product-grade offering, never
    that some particular host is running it. The state comes from the
    deployment's own catalog through /console/status — so the console
    is consistent between STT (statically production since M31) and
    TTS (promoted at M42), and goes back to Coming Soon the moment a
    rollback removes the route."""

    async def test_a_promoted_service_reads_production_from_the_catalog(
        self, settings: Settings, db_engine: AsyncEngine
    ) -> None:
        async with client_with_db(settings, db_engine) as (client, _factory):
            payload = (await client.get("/console/status")).json()
        assert payload["services"]["tts"]["status"] == "production"
        assert payload["services"]["tts"]["languages"] == ["en", "hi"]

    async def test_the_environment_never_changes_the_badge(
        self, settings: Settings, db_engine: AsyncEngine
    ) -> None:
        # The badge is a PRODUCT claim: a dev/staging box and a prod box
        # serving the same catalog must say the same thing. (Whether the
        # service is actually RUNNING is /health/ready's question.)
        from fastapi import FastAPI

        from intelliai_api.core.config import Environment

        answers = set()
        for environment in (Environment.DEV, Environment.PROD):
            scoped = settings.model_copy(update={"env": environment})

            def use(app: FastAPI, scoped: Settings = scoped) -> None:
                app.state.settings = scoped

            async with client_with_db(settings, db_engine, use) as (client, _factory):
                payload = (await client.get("/console/status")).json()
                answers.add(payload["services"]["tts"]["status"])
        assert answers == {"production"}

    async def test_the_rollback_posture_says_coming_soon_again(
        self, settings: Settings, db_engine: AsyncEngine
    ) -> None:
        # The UI half of the M42 rollback proof: compose the registry the
        # revert commit would produce (refusal route, no Hindi voices)
        # and the console goes back to promising nothing.
        from fastapi import FastAPI

        from intelliai_api.registry.catalog import _ARTIFACTS, _MODELS, _ROUTES, _VOICES
        from intelliai_api.registry.proposals import ROLLBACK_TTS_PRODUCTION_ROUTE
        from intelliai_api.registry.registry import Registry

        rolled_back = Registry(
            artifacts=_ARTIFACTS,
            models=_MODELS,
            voices=tuple(v for v in _VOICES if not v.id.startswith("hindi-")),
            routes=tuple(
                ROLLBACK_TTS_PRODUCTION_ROUTE
                if (r.public_model_id == "intelliai-tts" and r.selector.language == "hi")
                else r
                for r in _ROUTES
            ),
        )

        def as_rolled_back(app: FastAPI) -> None:
            app.state.registry = rolled_back

        async with client_with_db(settings, db_engine, as_rolled_back) as (client, _factory):
            payload = (await client.get("/console/status")).json()
        assert payload["services"]["tts"]["status"] == "soon"
        assert payload["services"]["tts"]["languages"] == ["en"]

    async def test_status_payload_carries_no_engine_vocabulary(
        self, settings: Settings, db_engine: AsyncEngine
    ) -> None:
        async with client_with_db(settings, db_engine) as (client, _factory):
            body = (await client.get("/console/status")).text.lower()
        for banned in ("kokoro", "espeak", "hf_alpha", "hm_psi", "whisper", "qwen"):
            assert banned not in body

    async def test_keys_page_defaults_are_production_safe(
        self, settings: Settings, db_engine: AsyncEngine
    ) -> None:
        # The STATIC page keeps TTS in the Coming Soon list; the Preview
        # chip exists but ships hidden — only /console/status reveals it.
        async with client_with_db(settings, db_engine) as (client, _factory):
            page = (await client.get("/console/keys")).text
        assert "IntelliAI TTS, OCR, Translate, Vision, and LLM — Coming Soon" in page
        assert 'id="tts-status-chip"' in page
        assert "badge-soon hidden" in page  # hidden until the catalog says otherwise
        # No launch word is hardcoded on the page: the chip is labelled
        # at runtime by the shared status model.
        assert "IntelliAI TTS · Preview" not in page
        assert "IntelliAI TTS · Production" not in page
        assert "withStatus" in page

    async def test_services_and_home_render_through_the_status_model(
        self, settings: Settings, db_engine: AsyncEngine
    ) -> None:
        async with client_with_db(settings, db_engine) as (client, _factory):
            services = (await client.get("/console/services")).text
            home = (await client.get("/console/home")).text
        assert "IntelliAI.withStatus" in services
        assert "IntelliAI.badgeFor" in services
        assert "IntelliAI.withStatus" in home
        # No page hardcodes the preview claim as a string literal — the
        # badge text must come from the shared model (badgeFor).
        assert '"Preview"' not in services
        assert '"Preview"' not in home


class TestSttShare:
    """M46 — the Playground's Share button: a user-initiated export of
    the visible transcript TEXT only, through the browser/OS native
    share sheet, with a clipboard fallback. Frontend-only feature; the
    page is static JS, so these tests pin the served source's behavior
    the same way the usage/status suites do."""

    async def _studio(self, settings: Settings, db_engine: AsyncEngine) -> str:
        async with client_with_db(settings, db_engine) as (client, _factory):
            return (await client.get("/console/playground")).text

    async def test_share_exists_hidden_until_a_transcript_does(
        self, settings: Settings, db_engine: AsyncEngine
    ) -> None:
        page = await self._studio(settings, db_engine)
        # (A/B) the button ships hidden and is revealed only by the
        # refresh law: never while a request is in flight, never empty.
        assert 'class="btn hidden" id="share"' in page
        assert "function refreshShareButton()" in page
        assert "var busy = transcribeBtn.disabled;" in page
        assert "var hasText = transcript.value.trim().length > 0;" in page
        assert 'shareBtn.classList.toggle("hidden", busy || !hasText);' in page
        # wired into every lifecycle edge: submit, settle, and edits.
        assert page.count("refreshShareButton();") >= 3
        assert 'transcript.addEventListener("input"' in page

    async def test_native_share_gets_title_and_snapshot_text_only(
        self, settings: Settings, db_engine: AsyncEngine
    ) -> None:
        page = await self._studio(settings, db_engine)
        # (C/D/J) runtime feature detection, the exact clean payload,
        # and the click-time snapshot (corrections share what is seen).
        assert 'typeof navigator.share === "function"' in page
        assert 'navigator.share({ title: "IntelliAI STT Transcript", text: shareText })' in page
        assert "var shareText = transcript.value.trim();" in page
        # (L) the app never shortens the payload on its own.
        assert "shareText.slice" not in page
        assert "shareText.substring" not in page

    async def test_cancelling_the_share_sheet_is_not_an_error(
        self, settings: Settings, db_engine: AsyncEngine
    ) -> None:
        page = await self._studio(settings, db_engine)
        # (F) AbortError = the user changed their mind; stay silent.
        assert 'if (error && error.name === "AbortError") return;' in page
        assert "Share failed" not in page

    async def test_unsupported_browsers_fall_back_to_the_clipboard(
        self, settings: Settings, db_engine: AsyncEngine
    ) -> None:
        page = await self._studio(settings, db_engine)
        # (G/H/I) fallback chain with friendly words at every rung.
        assert "function shareFallbackCopy(" in page
        assert "navigator.clipboard.writeText(shareText)" in page
        assert "Sharing isn't supported here. Transcript copied to clipboard." in page
        assert "Sharing didn't work here — transcript copied to clipboard instead." in page
        assert "Sharing isn't supported in this browser." in page

    async def test_share_is_frontend_only_and_consent_free(
        self, settings: Settings, db_engine: AsyncEngine
    ) -> None:
        page = await self._studio(settings, db_engine)
        # (Phase 13/14) the share handler block reaches neither the
        # network nor the consent checkbox: between the share section
        # marker and the transcribe handler there is no fetch/apiJSON
        # and no contribution read.
        share_block = page.split("── Share (M46)")[1].split("transcribeBtn.addEventListener")[0]
        assert "fetch(" not in share_block
        assert "apiJSON" not in share_block
        assert "contribute" not in share_block

    async def test_share_payload_carries_no_internal_vocabulary(
        self, settings: Settings, db_engine: AsyncEngine
    ) -> None:
        page = await self._studio(settings, db_engine)
        # (J/Phase 19) nothing but the transcript text enters the
        # payload: no IDs, no model names, no developer details. The
        # global public-product sweep already bans engine words on the
        # whole page; here we pin the share call itself.
        call = page.split("navigator.share({")[1].split("})")[0]
        assert "title" in call and "shareText" in call
        for banned in ("model", "request", "sample", "dev-", "language", "key"):
            assert banned not in call

    async def test_share_is_reachable_and_labelled_for_everyone(
        self, settings: Settings, db_engine: AsyncEngine
    ) -> None:
        page = await self._studio(settings, db_engine)
        # (K) a real <button> (keyboard-reachable by nature), with an
        # accessible name and a text label beside the icon, and a
        # polite live region for its feedback.
        assert 'aria-label="Share transcript"' in page
        assert "📤 Share</button>" in page
        assert 'id="share-note" role="status"' in page
