# Smart Investigator - Smart Views

* By Mitchell Jeffery
* 15 Feb 2026
* 1 min

---

Smart Views allow agents to render select components in the right-hand workflow panel. Components are UI elements that can display provided data from a JSON schema.

| Key | Description | Value Type | Example |
| :--- | :--- | :--- | :--- |
| `type` | The component type | `"markdown"` | `type: "markdown"` |
| `data` | The component data | dict | `data: {}` |

---

## Smart View Container

Smart Views can be used within a Workflow Stage artifact. You can include multiple Smart View containers when sending a Workflow Stage artifact.

You should only pass Smart View artifacts to the `data` property of a Smart View container.

### Schema

```json
{
  "type": "smart_view",
  "data": []
}
```

---

## Components

### Markdown

Markdown components allow you to format text with the following syntax.

| Element | Markdown Syntax |
| :--- | :--- |
| Heading | `# H1` `## H2` `### H3` |
| Bold | `**bold text**` |
| Italic | `*italicized text*` |
| Blockquote | `> blockquote` |
| Ordered List | `1. First item` `2. Second item` |
| Unordered List | `- First item` `- Second item` |
| Code | `` `code` `` |
| Horizontal Rule | `---` |
| Link | `[title](https://www.example.com)` |
| Image | `![alt text](image.jpg)` |

```json
{
  "type": "markdown",
  "data": {
    "content": "# Hello World!"
  }
}
```

---

### Confidence Score

```json
{
  "type": "confidence_score",
  "data": {
    "score": 0.5,
    "reasoning": "The score is based off x, y and z"
  }
}
```

---

### Feedback

```json
{
  "type": "feedback",
  "data": {
    "question": "Was this helpful?"
  }
}
```
