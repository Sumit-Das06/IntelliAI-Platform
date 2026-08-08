// IntelliAI Keyboard — a self-contained Android Gradle project.
//
// Deliberately NOT a uv workspace member (ADR-0001 scopes that rule to
// Python components). The keyboard is a CLIENT of the IntelliAI platform:
// it will consume only the public HTTPS API (Commit 13B+) and must never
// import backend code, reach PostgreSQL/MinIO, or talk to internal
// runtimes. apps/* may depend on packages/* only — this app depends on
// nothing internal at all.

pluginManagement {
    repositories {
        google {
            content {
                includeGroupByRegex("com\\.android.*")
                includeGroupByRegex("com\\.google.*")
                includeGroupByRegex("androidx.*")
            }
        }
        mavenCentral()
        gradlePluginPortal()
    }
}

dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
    }
}

rootProject.name = "intelliai-keyboard"
include(":app")
