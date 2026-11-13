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

## ollama:qwen3:14b: 10 of 15 as expected, 0 fell back to the stand-in, 4.6 s per request

| Request | Expected | Got | Code checks dropped or flagged | s |
|---|---|---|---|---|
| Java with Python in London | show | act ✗ |  | 10.7 |
| Java Python devs in London | ask | act ✗ |  | 3.8 |
| senior Java developers | ask | ask |  | 5.1 |
| Python devs near London | show | act ✗ |  | 3.7 |
| Python devs in London | act | act |  | 3.6 |
| React people available now | ask | act ✗ |  | 3.1 |
| SAP MM consultant | show | show |  | 3.2 |
| Java AND Python in London, 5+ years | act | act |  | 4.9 |
| Java developers in London | act | act |  | 3.9 |
| Python and AWS people with Senior in the title | show | ask ✗ |  | 5.7 |
| open jobs in London | act | act |  | 4.1 |
| Java developers at Bluefin | ask | ask |  | 4.5 |
| hello | nothing | nothing |  | 3.8 |
| candidates named Matin | nothing | nothing |  | 4.5 |
| Java developers near Narnia | act | act | location 'Narnia' (not in the data) | 4.4 |

