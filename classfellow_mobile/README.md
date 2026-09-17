# ClassFellow Mobile Client (Flutter 3.x)

ClassFellow Mobile is the cross-platform client for Teachers and Parents built with Flutter 3.x, integrating with the ClassFellow Django REST Framework Mobile API Gateway.

## Architecture

- **`lib/core/theme/`**: ClassFellow Slate-900 / Emerald design tokens (`#0F172A`, `#1E293B`, `#10B981`).
- **`lib/core/network/`**: `ApiClient` with automated `Authorization: Token <key>` interceptors and 10-second connection timeouts.
- **`lib/core/storage/`**: `SecureStorageService` for persisting tokens, roles, and profiles.
- **`lib/models/`**: Strongly typed data transfer objects for Teacher and Parent workflows.
- **`lib/features/auth/`**: Branded authentication screen with role-directed navigation.
- **`lib/features/teacher/`**: Assigned class allocations, date-selectable attendance roster, and bounds-validated marks submission.
- **`lib/features/parent/`**: Multi-child switcher, fee ledger breakdown, monthly attendance calendar, and examination scorecards.

## Getting Started

```bash
flutter pub get
flutter run
```
