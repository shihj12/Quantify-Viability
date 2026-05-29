<script lang="ts">
  // Top-level router. The current screen is driven by the central session store;
  // mounting/unmounting the threshold/review components mirrors the desktop's
  // QStackedWidget. A beforeunload autosave best-effort persists the session.

  import { onMount } from "svelte";
  import { session } from "@/state/session.svelte";
  import LoadScreen from "@/screens/LoadScreen.svelte";
  import ThresholdScreen from "@/screens/ThresholdScreen.svelte";
  import ReviewScreen from "@/screens/ReviewScreen.svelte";

  onMount(() => {
    const onBeforeUnload = () => {
      if (session.project) void session.autosave();
    };
    window.addEventListener("beforeunload", onBeforeUnload);
    return () => window.removeEventListener("beforeunload", onBeforeUnload);
  });
</script>

{#if session.screen === "load"}
  <LoadScreen />
{:else if session.screen === "threshold"}
  <ThresholdScreen />
{:else if session.screen === "review"}
  <ReviewScreen />
{/if}

<style>
  :global(body) {
    margin: 0;
    background: #0f0f14;
    color: #e6e6e6;
    font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  }
  :global(*) {
    box-sizing: border-box;
  }
</style>
