## rules: 15 of 15 as expected, 0 fell back to the stand-in, 0.0 s per request

| Request | Expected | Got | Code checks dropped or flagged | s |
|---|---|---|---|---|
| Java with Python in London | show | show |  | 0.0 |
| Java Python devs in London | ask | ask |  | 0.0 |
| senior Java developers | ask | ask |  | 0.0 |
| Python devs near London | show | show |  | 0.0 |
| Python devs in London | act | act |  | 0.0 |
| React people available now | ask | ask |  | 0.0 |
| SAP MM consultant | show | show |  | 0.0 |
| Java AND Python in London, 5+ years | act | act |  | 0.0 |
| Java developers in London | act | act |  | 0.0 |
| Python and AWS people with Senior in the title | show | show |  | 0.0 |
| open jobs in London | act | act |  | 0.0 |
| Java developers at Bluefin | ask | ask |  | 0.0 |
| hello | nothing | nothing |  | 0.0 |
| candidates named Matin | nothing | nothing |  | 0.0 |
| Java developers near Narnia | act | act | “near Narnia” (not a place in the data) | 0.0 |

## ollama:qwen3:14b: 10 of 15 as expected, 0 fell back to the stand-in, 4.1 s per request

| Request | Expected | Got | Code checks dropped or flagged | s |
|---|---|---|---|---|
| Java with Python in London | show | act ✗ |  | 10.2 |
| Java Python devs in London | ask | act ✗ |  | 3.5 |
| senior Java developers | ask | ask |  | 4.9 |
| Python devs near London | show | act ✗ |  | 3.5 |
| Python devs in London | act | act |  | 3.3 |
| React people available now | ask | act ✗ |  | 2.9 |
| SAP MM consultant | show | show |  | 3.0 |
| Java AND Python in London, 5+ years | act | act |  | 4.3 |
| Java developers in London | act | act |  | 3.3 |
| Python and AWS people with Senior in the title | show | ask ✗ |  | 5.0 |
| open jobs in London | act | act |  | 3.4 |
| Java developers at Bluefin | ask | ask |  | 4.2 |
| hello | nothing | nothing |  | 3.5 |
| candidates named Matin | nothing | nothing |  | 3.6 |
| Java developers near Narnia | act | act | location 'Narnia' (not in the data) | 3.5 |

