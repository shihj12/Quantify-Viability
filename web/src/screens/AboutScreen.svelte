<script lang="ts">
  // About page — placeholder. Reachable from Home.
  import { session } from "@/state/session.svelte";
</script>

<div class="page">
  <header>
    <h1>About</h1>
  </header>
  <div class="body">
    <p class="muted">Content coming soon.</p>
  </div>
  <footer>
    <button onclick={() => session.go("load")}>← Back to Home</button>
  </footer>
</div>

<style>
  .page {
    display: flex;
    flex-direction: column;
    min-height: 100vh;
    padding: 32px 40px;
    box-sizing: border-box;
    max-width: 760px;
    margin: 0 auto;
  }
  header h1 {
    font-size: 1.6rem;
  }
  .body {
    flex: 1;
    padding: 24px 0;
  }
  .muted {
    color: #888;
    font-size: 0.95rem;
  }
  footer {
    padding-top: 16px;
    border-top: 1px solid #2a2a2a;
  }
  button {
    background: #2c2c3a;
    color: #eee;
    border: 1px solid #3a3a4a;
    border-radius: 6px;
    padding: 8px 16px;
    cursor: pointer;
    font-size: 0.9rem;
  }
  button:hover {
    background: #353548;
  }
</style>
