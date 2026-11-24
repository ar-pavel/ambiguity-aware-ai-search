# Scripted evaluation: bedrock

42 requests (12 clear controls), 80 cases, θ = 0.5, run on 2026-11-24. Rule, stand-in, search and data unchanged since v1.2-a2: yes.
Acting on the first reading gives a wrong list for 17.25 of the requests; 13.75 are high impact.

All figures are in requests. Each request counts once however many meanings it has.

| Strategy | Noticing rate | Questions | Needless questions | Wrong lists | High-impact wrong | Wrong on clear | Refused | Edits |
|---|---|---|---|---|---|---|---|---|
| always act | 1.0 | 0.0 | 0.0 | 17.25 | 13.75 | 0.0 | 0.0 | 0.0 |
| always show | 1.0 | 0.0 | 0.0 | 6.0 | 3.5 | 0.0 | 0.0 | 12.0 |
| always show | 0.75 | 0.0 | 0.0 | 8.859 | 6.109 | 0.0 | 0.0 | 9.0 |
| always show | 0.5 | 0.0 | 0.0 | 11.688 | 8.688 | 0.0 | 0.0 | 6.0 |
| always show | 0.25 | 0.0 | 0.0 | 14.484 | 11.234 | 0.0 | 0.0 | 3.0 |
| always ask | 1.0 | 22.0 | 10.0 | 6.25 | 3.75 | 0.0 | 0.0 | 0.5 |
| always ask | 0.75 | 22.0 | 10.0 | 6.375 | 3.875 | 0.0 | 0.0 | 0.375 |
| always ask | 0.5 | 22.0 | 10.0 | 6.5 | 4.0 | 0.0 | 0.0 | 0.25 |
| always ask | 0.25 | 22.0 | 10.0 | 6.625 | 4.125 | 0.0 | 0.0 | 0.125 |
| adaptive | 1.0 | 14.0 | 6.0 | 6.25 | 3.75 | 0.0 | 0.0 | 4.5 |
| adaptive | 0.75 | 14.0 | 6.0 | 7.375 | 4.625 | 0.0 | 0.0 | 3.375 |
| adaptive | 0.5 | 14.0 | 6.0 | 8.5 | 5.5 | 0.0 | 0.0 | 2.25 |
| adaptive | 0.25 | 14.0 | 6.0 | 9.625 | 6.375 | 0.0 | 0.0 | 1.125 |

## The rule at other thresholds

| θ | Questions | Wrong lists at noticing rate 1.0 | 0.75 | 0.5 | 0.25 |
|---|---|---|---|---|---|
| 0.1 | 7.0 | 6.25 | 8.172 | 10.062 | 11.922 |
| 0.2 | 11.0 | 6.25 | 7.75 | 9.25 | 10.75 |
| 0.3 | 13.0 | 6.25 | 7.5 | 8.75 | 10.0 |
| 0.4 | 13.0 | 6.25 | 7.5 | 8.75 | 10.0 |
| 0.5 | 14.0 | 6.25 | 7.375 | 8.5 | 9.625 |
| 0.6 | 14.0 | 6.25 | 7.375 | 8.5 | 9.625 |
| 0.7 | 14.0 | 6.25 | 7.375 | 8.5 | 9.625 |
| 0.8 | 14.0 | 6.25 | 7.375 | 8.5 | 9.625 |
| 0.9 | 14.0 | 6.25 | 7.375 | 8.5 | 9.625 |

## Every case

| Case | Request | Meant | Wanted | Lost | Unwanted | High impact | act / show / ask / adaptive | Still wrong when everything shown is noticed |
|---|---|---|---|---|---|---|---|---|
| c01 | Go developers in Manchester | Go · Manchester | 4 | 0 | 0 |  | act / show / act / act |  |
| c02 | Go AND Kubernetes engineers | Go AND Kubernetes | 9 | 0 | 0 |  | act / show / act / act |  |
| c03 | React OR Vue developers in London | React OR Vue · London | 11 | 0 | 0 |  | act / show / act / act |  |
| c04 | Terraform engineers in Leeds | Terraform · Leeds | 1 | 0 | 0 |  | act / show / act / act |  |
| c05 | SQL developers with 8+ years | SQL · 8+ years | 21 | 0 | 0 |  | act / show / act / act |  |
| c06 | remote Python developers | Python · remote | 19 | 0 | 0 |  | act / show / act / act |  |
| c07 | open jobs in Manchester | open jobs · Manchester | 1 | 0 | 0 |  | act / show / act / act |  |
| c08 | Kotlin developers in London | Kotlin · London | 7 | 0 | 0 |  | act / show / act / act |  |
| c09 | AWS engineers in the UK | AWS · UK | 54 | 0 | 0 |  | act / show / act / act |  |
| c10 | JavaScript developers in Dublin with 3+ years | JavaScript · Dublin · 3+ years | 3 | 0 | 0 |  | act / show / act / act |  |
| c11 | hybrid Java developers in Leeds | Java · Leeds · hybrid | 1 | 0 | 0 |  | act / show / act / act |  |
| c12 | Python AND SQL AND AWS people in London | Python AND SQL AND AWS · London | 1 | 0 | 0 |  | act / show / act / act |  |
| k01.1 | Python and AWS engineers in London | Python AND AWS · London | 11 | 0 | 0 |  | act / show / ask / show |  |
| k01.2 | Python and AWS engineers in London | Python OR AWS · London | 42 | 31 | 0 | yes | act / show / ask / show | always act |
| k02.1 | Java and Kotlin developers | Java AND Kotlin | 11 | 0 | 0 |  | act / show / ask / show |  |
| k02.2 | Java and Kotlin developers | Java OR Kotlin | 47 | 36 | 0 | yes | act / show / ask / show | always act |
| k03.1 | React with TypeScript developers | React AND TypeScript | 1 | 0 | 0 |  | act / show / ask / show |  |
| k03.2 | React with TypeScript developers | React OR TypeScript | 22 | 21 | 0 | yes | act / show / ask / show | always act |
| k04.1 | Go or Python people in Manchester | Go AND Python · Manchester | 0 | 0 | 10 | yes | act / show / ask / show | always act |
| k04.2 | Go or Python people in Manchester | Go OR Python · Manchester | 10 | 0 | 0 |  | act / show / ask / show |  |
| k05.1 | Kubernetes Terraform engineers | Kubernetes AND Terraform | 4 | 0 | 0 |  | act / show / ask / ask |  |
| k05.2 | Kubernetes Terraform engineers | Kubernetes OR Terraform | 30 | 26 | 0 | yes | act / show / ask / ask | always act |
| k06.1 | Java/Python developers in Birmingham | Java AND Python · Birmingham | 1 | 0 | 0 |  | act / show / ask / ask |  |
| k06.2 | Java/Python developers in Birmingham | Java OR Python · Birmingham | 6 | 5 | 0 | yes | act / show / ask / ask | always act |
| k07.1 | SQL, Python developers in Leeds | SQL AND Python · Leeds | 0 | 0 | 0 |  | act / show / ask / ask |  |
| k07.2 | SQL, Python developers in Leeds | SQL OR Python · Leeds | 4 | 4 | 0 | yes | act / show / ask / ask | always act |
| k08.1 | developers who know JavaScript plus React in London | JavaScript AND React · London | 5 | 0 | 0 |  | act / show / ask / show |  |
| k08.2 | developers who know JavaScript plus React in London | JavaScript OR React · London | 13 | 8 | 0 | yes | act / show / ask / show | always act |
| s01.1 | senior Python developers in London | Python · London · 5+ years | 19 | 0 | 0 |  | act / show / ask / ask |  |
| s01.2 | senior Python developers in London | Python · London · 'Senior' in title | 6 | 1 | 14 | yes | act / show / ask / ask | always act |
| s02.1 | senior Java engineers in Manchester | Java · Manchester · 5+ years | 7 | 0 | 0 |  | act / show / ask / ask |  |
| s02.2 | senior Java engineers in Manchester | Java · Manchester · 'Senior' in title | 2 | 0 | 5 | yes | act / show / ask / ask | always act |
| s03.1 | lead AWS engineers | AWS · 5+ years | 43 | 0 | 0 |  | act / show / ask / ask |  |
| s03.2 | lead AWS engineers | AWS · 'Lead' in title | 4 | 1 | 40 | yes | act / show / ask / ask | always act |
| s04.1 | lead Python developers | Python · 5+ years | 50 | 0 | 0 |  | act / show / ask / ask |  |
| s04.2 | lead Python developers | Python · 'Lead' in title | 1 | 0 | 49 | yes | act / show / ask / ask | always act |
| s05.1 | experienced Go developers | Go · 5+ years | 24 | 0 | 6 |  | act / show / act / act | always act, always show, always ask, adaptive |
| s05.2 | experienced Go developers | Go · 'Senior' in title | 10 | 0 | 20 | yes | act / show / act / act | always act, always show, always ask, adaptive |
| s06.1 | Java team leads in London | Java · London · 5+ years | 15 | 0 | 0 |  | act / show / ask / ask |  |
| s06.2 | Java team leads in London | Java · London · 'Lead' in title | 2 | 1 | 14 | yes | act / show / ask / ask | always act |
| l01.1 | Java developers near London | Java · London | 21 | 0 | 10 |  | act / show / act / act | always act, always show, always ask, adaptive |
| l01.2 | Java developers near London | Java · London and nearby | 31 | 0 | 0 |  | act / show / act / act |  |
| l02.1 | React developers around London | React · London | 9 | 0 | 4 |  | act / show / act / act | always act, always show, always ask, adaptive |
| l02.2 | React developers around London | React · London and nearby | 13 | 0 | 0 |  | act / show / act / act |  |
| l03.1 | SQL people in the London area | SQL · London | 13 | 0 | 12 |  | act / show / ask / show | always act |
| l03.2 | SQL people in the London area | SQL · London and nearby | 25 | 0 | 0 |  | act / show / ask / show |  |
| l04.1 | AWS engineers who can commute to London | AWS · London | 24 | 0 | 16 |  | act / show / act / act | always act, always show, always ask, adaptive |
| l04.2 | AWS engineers who can commute to London | AWS · London and nearby | 40 | 0 | 0 |  | act / show / act / act |  |
| a01.1 | Java developers in London available immediately | Java · London · can start now | 2 | 0 | 0 |  | act / show / act / act |  |
| a01.2 | Java developers in London available immediately | Java · London · notice ≤ 2 weeks | 12 | 10 | 0 | yes | act / show / act / act | always act, always show, always ask, adaptive |
| a02.1 | Python people who can start asap | Python · can start now | 14 | 0 | 0 |  | act / show / ask / show |  |
| a02.2 | Python people who can start asap | Python · notice ≤ 2 weeks | 35 | 21 | 0 | yes | act / show / ask / show | always act |
| a03.1 | available AWS engineers in Manchester | AWS · Manchester · can start now | 2 | 0 | 0 |  | act / show / ask / show |  |
| a03.2 | available AWS engineers in Manchester | AWS · Manchester · notice ≤ 2 weeks | 3 | 1 | 0 |  | act / show / ask / show | always act |
| a04.1 | SQL developers free to start straight away | SQL · can start now | 6 | 0 | 0 |  | act / show / act / act |  |
| a04.2 | SQL developers free to start straight away | SQL · notice ≤ 2 weeks | 20 | 14 | 0 | yes | act / show / act / act | always act, always show, always ask, adaptive |
| a05.1 | Go developers who can start soon | Go · notice ≤ 2 weeks | 15 | 9 | 0 | yes | act / show / ask / ask | always act |
| a05.2 | Go developers who can start soon | Go · notice ≤ 1 month | 26 | 20 | 0 | yes | act / show / ask / ask | always act, always show, always ask, adaptive |
| t01.1 | Python at Northwind | Python · works at Northwind Labs | 3 | 0 | 0 |  | act / show / ask / ask |  |
| t01.2 | Python at Northwind | jobs · Python · at Northwind Labs | 0 | 0 | 3 | yes | act / show / ask / ask | always act |
| t02.1 | Java developers at Moorgate Payments | Java · works at Moorgate Payments | 7 | 0 | 0 |  | act / show / ask / ask |  |
| t02.2 | Java developers at Moorgate Payments | jobs · Java · at Moorgate Payments | 0 | 0 | 7 | yes | act / show / ask / ask | always act |
| t03.1 | Ironbridge Bank SQL engineers | SQL · works at Ironbridge Bank | 1 | 0 | 0 |  | act / show / ask / ask |  |
| t03.2 | Ironbridge Bank SQL engineers | jobs · SQL · at Ironbridge Bank | 0 | 0 | 1 | yes | act / show / ask / ask | always act |
| m01.1 | senior Java Python developers | Java AND Python · 5+ years | 11 | 0 | 0 |  | act / show / ask / ask |  |
| m01.2 | senior Java Python developers | Java OR Python · 5+ years | 74 | 63 | 0 | yes | act / show / ask / ask | always act |
| m01.3 | senior Java Python developers | Java AND Python · 'Senior' in title | 3 | 1 | 9 | yes | act / show / ask / ask | always act |
| m01.4 | senior Java Python developers | Java OR Python · 'Senior' in title | 22 | 20 | 9 | yes | act / show / ask / ask | always act |
| m02.1 | Python or Go engineers available now | Python AND Go · can start now | 3 | 0 | 14 | yes | act / show / act / act | always act, always ask, adaptive |
| m02.2 | Python or Go engineers available now | Python OR Go · can start now | 17 | 0 | 0 |  | act / show / act / act |  |
| m02.3 | Python or Go engineers available now | Python AND Go · notice ≤ 2 weeks | 5 | 2 | 14 | yes | act / show / act / act | always act, always show, always ask, adaptive |
| m02.4 | Python or Go engineers available now | Python OR Go · notice ≤ 2 weeks | 45 | 28 | 0 | yes | act / show / act / act | always act, always show, always ask, adaptive |
| m03.1 | lead Kubernetes engineers near London | Kubernetes · London · 5+ years | 8 | 0 | 7 |  | act / show / ask / ask | always act, always show, always ask, adaptive |
| m03.2 | lead Kubernetes engineers near London | Kubernetes · London · 'Lead' in title | 1 | 0 | 14 | yes | act / show / ask / ask | always act, always show, always ask, adaptive |
| m03.3 | lead Kubernetes engineers near London | Kubernetes · London and nearby · 5+ years | 15 | 0 | 0 |  | act / show / ask / ask |  |
| m03.4 | lead Kubernetes engineers near London | Kubernetes · London and nearby · 'Lead' in title | 2 | 0 | 13 | yes | act / show / ask / ask | always act |
| m04.1 | experienced AWS engineers who can start soon | AWS · 5+ years · notice ≤ 2 weeks | 19 | 0 | 38 | yes | act / show / act / act | always act, always show, always ask, adaptive |
| m04.2 | experienced AWS engineers who can start soon | AWS · 'Senior' in title · notice ≤ 2 weeks | 7 | 0 | 50 | yes | act / show / act / act | always act, always show, always ask, adaptive |
| m04.3 | experienced AWS engineers who can start soon | AWS · 5+ years · notice ≤ 1 month | 35 | 0 | 22 |  | act / show / act / act | always act, always show, always ask, adaptive |
| m04.4 | experienced AWS engineers who can start soon | AWS · 'Senior' in title · notice ≤ 1 month | 14 | 0 | 43 | yes | act / show / act / act | always act, always show, always ask, adaptive |
