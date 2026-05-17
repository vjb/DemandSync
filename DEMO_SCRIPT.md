# DemandSync V2 - Hackathon Demo Script (3 Minutes)

**Objective**: This choreography is designed to highlight the Google Cloud Rapid Agent Hackathon requirements (MongoDB Track).

### [0:00 - 0:30] Introduction & Architecture
- **Action:** Open the deployed Cloud Run URL.
- **Voiceover:** "Welcome to DemandSync V2. We've built an autonomous retail logistics platform using Google Cloud Agent Builder, Vertex AI, and MongoDB Atlas Vector Search. All of this is deployed on a fully serverless Cloud Run container."
- **Action:** Briefly show the `Dockerfile` and `deploy.sh` script to prove containerization.

### [0:30 - 1:15] The Environmental Trigger & MongoDB Atlas
- **Action:** Open the scenario dropdown and select "Category 4 Blizzard hitting Central Park". Click **Run Simulation**.
- **Voiceover:** "When an anomaly strikes, our system doesn't rely on keyword tags. We generate a text-embedding-004 vector and execute a massive `$vectorSearch` directly against our live MongoDB Atlas database."
- **Action:** Point to the **MongoDB Atlas Vector Search** telemetry pillar lighting up in real-time.
- **Voiceover:** "We combine vector similarity with `$geoNear` geospatial filtering to instantly identify matching inventory in our Midtown warehouse within a 5-mile radius."

### [1:15 - 2:00] Google Cloud Agent Builder Compliance
- **Action:** The simulation calculates a dynamic surge price.
- **Voiceover:** "We don't let AI hallucinates prices. We grounded our FinOps agent using **Google Cloud Agent Builder**."
- **Action:** Point to the *Pricing Reasoning* text. 
- **Voiceover:** "Vertex AI Search queries our unstructured Data Store containing our strict corporate pricing policy. Notice how the agent explicitly caps the Blizzard markup at 15% to prevent price gouging, perfectly adhering to our institutional constraints."

### [2:00 - 2:45] Parallel Multimodal Asset Generation
- **Action:** Wait for the `Google Vertex AI & Gemini` pillar to finish generating.
- **Voiceover:** "Once compliance is verified, the agent swarm fires off parallel generative tasks. Gemini 3.1 Pro synthesizes multi-channel copy while Imagen 3.0 generates beautiful A/B visual assets simultaneously."
- **Action:** Point to the two distinct visual variants and the A/B testing CTR readout on the screen.
- **Voiceover:** "Because we use `asyncio.gather` for parallel synthesis, we get double the output without doubling the latency."

### [2:45 - 3:00] Copilot Fine-Tuning & Completion
- **Action:** Type into the Purple Copilot Terminal: *"Pivot strategy to Gen-Z"* and click **Refine Strategy**.
- **Voiceover:** "Finally, our human operators aren't locked out. Using the Copilot UI, we can inject mid-flight constraints, instantly pivoting the multimodal generation."
- **Action:** The new Gen-Z focused copy and image appear. 
- **Voiceover:** "Thank you for watching the DemandSync V2 demonstration."
