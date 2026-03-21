# VideoBot SaaS - Technical Roadmap

This document outlines the strategic plan for evolving the VideoBot SaaS platform from its current state into a more robust, scalable, and feature-rich service. The roadmap is divided into phases, starting with foundational improvements and progressing towards advanced features and enterprise-readiness.

---

## Phase 1: Foundation & Production Hardening (✅ Completed)

This initial phase focused on stabilizing the existing codebase, ensuring core features are reliable, and preparing the application for scalable operations.

### Key Achievements:
- **Core Engine Fix**: Resolved a critical bug in the video generation pipeline caused by a `moviepy` library update. The dependency was pinned to a stable version (`<2.0.0`) to ensure consistent video processing.
- **Provider Integration Fix**: Corrected a bug in the ElevenLabs TTS integration where arguments were being passed incorrectly, ensuring reliable voice-over generation.
- **Multi-Tenancy & Security Hardening**: Patched a session-handling flaw in the YouTube uploader that risked cross-tenant data exposure. The system now correctly uses per-user authentication tokens.
- **Data Integrity & Connection Pooling**: Migrated the data access layer from raw `sqlite3` calls, which were causing connection leaks, to a managed **SQLAlchemy ORM**. This improves database connection management and overall stability.
- **UI/UX Enhancements**:
    - Made generated videos directly accessible via a new, authenticated `/videos/<filename>` endpoint.
    - Added visibility for processing errors on the user dashboard, so users are immediately aware of failed jobs.
- **Initial Scalability Refactor**: Decoupled the synchronous, in-process scheduler and manual generation triggers. All video generation jobs are now dispatched to a **Celery task queue** backed by Redis, preventing the web server from blocking and enabling background processing.

---

## Phase 2: Advanced Reliability & Observability (In Progress)

This phase focuses on building a production-grade monitoring and error-handling infrastructure.

### Initiatives:
- **1. Centralized Error & Performance Monitoring (Observability)**
    - **Status:** **DONE**
    - **Description:** Integrated the **Sentry SDK** for both the Flask application and Celery workers. All unhandled exceptions and performance data are now captured and aggregated in a central Sentry project. This provides deep insights into application health, performance bottlenecks, and user-impactful errors.
    - **Impact:** Moves from reactive (checking logs) to proactive error management. Speeds up debugging and improves overall service stability.

- **2. Idempotency & Task Retries (Reliability)**
    - **Status:** **Next Up**
    - **Description:** Enhance Celery tasks to be fully idempotent, meaning they can be run multiple times with the same input without causing duplicate actions (e.g., posting the same video twice). Implement automatic retry policies (e.g., exponential backoff) for tasks that fail due to transient network issues or temporary API provider unavailability.
    - **Impact:** Increases the success rate of video generation and publishing without manual intervention.

- **3. Advanced Metrics & Dashboarding (Observability)**
    - **Status:** **Planned**
    - **Description:** Integrate **Prometheus** for metrics collection and **Grafana** for visualization.
        - **Metrics to Track:** Celery queue length, task success/failure rates, task execution time, API provider response times, and system resource usage (CPU/memory).
    - **Impact:** Provides a real-time, high-level overview of system health and performance, enabling proactive scaling and issue detection.

---

## Phase 3: Scalability & Performance Optimization (Planned)

This phase aims to ensure the platform can handle a growing user base and increasing load.

### Initiatives:
- **1. Asynchronous Social Publishing**
    - **Description:** Decouple the social media upload process from the main generation task. Create separate, dedicated Celery tasks for each platform (YouTube, TikTok, etc.). A "parent" task will orchestrate the generation and then trigger the individual upload tasks.
    - **Impact:** Parallelizes the publishing process, provides granular control and status tracking for each platform, and isolates failures (e.g., a failed TikTok upload won't prevent a YouTube upload).

- **2. Celery Worker Auto-Scaling**
    - **Description:** Implement a mechanism to automatically scale the number of Celery workers based on the queue size and processing load. This is best achieved in a containerized environment (e.g., Docker + Kubernetes with Horizontal Pod Autoscaler).
    - **Impact:** Ensures resources are used efficiently, scaling up during peak demand and down during lulls to save costs, while maintaining a consistent quality of service.

- **3. Dedicated Media Processing Service**
    - **Description:** Offload video transcoding, watermarking, and other heavy media manipulations to a dedicated microservice or a cloud-based solution (e.g., AWS Elemental MediaConvert). The Celery worker would orchestrate these jobs rather than performing them directly.
    - **Impact:** Frees up Celery workers to focus on business logic, enables more complex video effects, and allows for specialized hardware optimization for media processing.

---

## Phase 4: Feature Expansion & Monetization (Future)

This phase focuses on adding new, user-facing features and implementing a business model.

### Initiatives:
- **1. Self-Service User Onboarding (UX)**
    - **Description:** Implement a public-facing registration page where users can sign up without admin intervention. This includes email verification and automatic creation of their initial tenant/workspace.
    - **Impact:** Reduces administrative overhead and allows for organic user growth.

- **2. Billing & Plan Management (Monetization)**
    - **Description:** Integrate a payment provider like **Stripe** to manage subscriptions and plans. Implement logic to gate features and enforce usage quotas (e.g., number of videos per month, access to premium features) based on the user's subscription tier.
    - **Impact:** Enables the platform to generate revenue.

- **3. Advanced Tenant & User Management (Admin)**
    - **Description:** Build out a more comprehensive admin dashboard for managing tenants, users, and roles. This would include features for inviting team members, setting permissions, and viewing tenant-wide usage analytics.
    - **Impact:** Prepares the platform for team- and enterprise-level customers.
