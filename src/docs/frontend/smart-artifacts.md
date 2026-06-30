# Smart Investigator - Smart Artifacts

* By Mitchell Jeffery
* 12 Mar 2026

---

Smart Artifacts are central to the smart investigator front-end framework. They allow Databricks agents to describe to the UI dynamically what is to be rendered on the front-end. The WebApp renders React components using the pre-built elements exposed via the framework. Their schema is simple; however, their data varies depending on the Smart Artifact types.

## Smart Artifact Types

### Workflow Stage

Workflow stages exist to break up a process into multiple steps. These stages are displayed in the right-hand workflow panel, and are tab stacked as each new stage is requested.

> **Stage names must be unique**
> If the stage name is the same as a previous name, it will overwrite the corresponding stage. This is intended and allows you to update or edit existing stages if required.

#### Workflow Stage Types

| Type | Description |
| :--- | :--- |
| form | Renders a Smart Form |
| view | Renders a Smart View |

#### Workflow Stage Schema

| Key | Description | Value Type | Example |
| :--- | :--- | :--- | :--- |
| name | The name and identifier for the workflow stage, displayed to the user on the frontend | str | `name: "Stage 1"` |
| data | The workflow stage data respective of the type | SmartForm \| SmartView | `data: []` |

#### Example

```json
{
  "type": "workflow_stage",
  "data": {
    "name": "Unique Stage Name",
    "data": []
  }
}
```

---

### Quick Action

Quick actions allow users to trigger actions via prompts instead of having to manually input the prompt. If multiple quick actions are provided they will be rendered next to each other. They are displayed in the left-hand conversational panel with the current message if any.

#### Quick Action Schema

| Key | Description | Value Type | Example |
| :--- | :--- | :--- | :--- |
| label | The label on the quick action button | str | `label: "End Task"` |
| prompt | The prompt sent on the user's behalf as a message | str | `prompt: "I would like to end the task"` |

#### Example

```json
{
  "type": "quick_action",
  "data": [
    {
      "label": "Quick Action",
      "prompt": "I would like to invoke a quick action"
    },
    {
      "label": "Say Hello",
      "prompt": "I would like you to say 'Hello World!'"
    }
  ]
}
```

---

### Alert

Alerts allow the agent to display an alert banner above the message composer. Note that alerts are not stored in the database and **will not** be displayed after refreshing the session page. To remove an Alert, send an Alert artifact with no data.

#### Alert Schema

| Key | Description | Value Type | Example |
| :--- | :--- | :--- | :--- |
| type | The alert type | `"info"` \| `"warning"` \| `"error"` | `type: "info"` |
| alert | The alert title | str | `alert: "Please Note"` |
| description | The alert description | str | `description: "This is an information alert"` |

#### Example

```json
{
  "type": "alert",
  "data": {
    "type": "info",
    "alert": "This is a warning",
    "description": "This is a description of the warning"
  }
}
```

---

### Quick Form

Quick forms allow an agent to gather further context via the message composer. They are limited to the types of data they can gather and are not stored in the database.

#### Quick Form Section Schema

| Key | Description | Value Type | Example |
| :--- | :--- | :--- | :--- |
| type | | `"section"` | `type: "section"` |
| title | The question title | str | `title: "What is this for?"` |
| data | The quick form input | QuickFormInput | `data: {}` |

#### Quick Form Input Schema

| Key | Description | Value Type | Example |
| :--- | :--- | :--- | :--- |
| type | The quick form input type | `"select"` \| `"multiselect"` | `type: "select"` |
| id | A unique identifier for the quick form input, included in the returned serialized data | str | `id: "1"` |
| required | Makes the quick form input skippable if false | bool | `required: true` |
| data | Defines the input data for the respective type (used for select, multiselect) | array[object] | `data: [{ value: "v1", label: "l1" }]` |
| maximum | Specifies the maximum allowed selections for the multiselect input | int | `maximum: 2` |

#### Example

```json
{
  "type": "quick_form",
  "data": [
    {
      "title": "What line of business does your investigation relate to?",
      "data": {
        "type": "select",
        "id": "lob",
        "required": true,
        "data": [
          { "value": "motor", "label": "Motor" },
          { "value": "property", "label": "Property" }
        ]
      }
    },
    {
      "title": "What is the current scope of the claim under investigation?",
      "data": {
        "type": "multiselect",
        "maximum": 3,
        "id": "scope",
        "required": false,
        "data": [
          { "value": "false_statements", "label": "False Statements" },
          { "value": "policy_inception", "label": "Policy Inception" },
          { "value": "non-disclosure_misrepresentation", "label": "Non-Disclosure Misrepresentation" },
          { "value": "policy_exclusions", "label": "Policy Exclusions" }
        ]
      }
    }
  ]
}
```

#### Quick Form Group Schema

| Key | Description | Value Type | Example |
| :--- | :--- | :--- | :--- |
| type | The quick form group type | `"lookup"` | `type: "lookup"` |
| id | A unique identifier for the quick form group | str | `id: "group1"` |
| data | Lookup options keyed by a field value | array | |
| metadata | References the field whose value drives the lookup | object | `metadata: { "fieldId": "lob" }` |

#### Lookup Group Example

```json
{
  "type": "quick_form",
  "data": [
    {
      "title": "What line of business does your investigation relate to?",
      "data": {
        "type": "select",
        "id": "lob",
        "required": true,
        "data": [
          { "value": "motor", "label": "Motor" },
          { "value": "property", "label": "Property" }
        ]
      }
    },
    {
      "title": "Please select the claims you want to investigate further",
      "data": {
        "type": "lookup",
        "id": "ABC123",
        "metadata": {
          "fieldId": "lob"
        },
        "data": [
          {
            "value": "motor",
            "component": {
              "type": "select",
              "id": "motor_claims",
              "required": true,
              "data": [
                { "value": "claim1", "label": "Motor Claim 1" },
                { "value": "claim2", "label": "Motor Claim 2" },
                { "value": "claim3", "label": "Motor Claim 3" }
              ]
            }
          },
          {
            "value": "property",
            "component": {
              "type": "select",
              "id": "property_claims",
              "required": true,
              "data": [
                { "value": "claim4", "label": "Property Claim 1" },
                { "value": "claim5", "label": "Property Claim 2" },
                { "value": "claim6", "label": "Property Claim 3" }
              ]
            }
          }
        ]
      }
    }
  ]
}
```

---

### Feedback

Feedback allows the agent to request feedback to be submitted by the user. It is displayed underneath the message it is requested on. Feedback is saved either against the message (if requested on a message) or a workflow stage (if requested during a workflow). All feedback is also sent to **GS**.

#### Feedback Schema

| Key | Description | Value Type | Example |
| :--- | :--- | :--- | :--- |
| type | | str | `type: "feedback"` |
| question | Question to display to the user | str | `question: "Please Provide Feedback"` |

#### Example

```json
{
  "type": "feedback",
  "data": {
    "question": "Please Provide Feedback"
  }
}
```

---

### Citation

Citation allows the agent to display sources used for their message response. It displays on the right side of the screen when toggled. Designed to render Markdown.

#### Citation Schema

| Key | Description | Value Type | Example |
| :--- | :--- | :--- | :--- |
| type | | str | `type: "citation"` |
| data | A list of Markdown strings to render | list[str] | `data: [{"content": "# Hello World!"}]` |

#### Example

```json
{
  "type": "citation",
  "data": [
    {"content": "### Document Title \n[Unit 2: None - Disclosure Misrepresentation](localhost:8080/) \n### Section Title \nEvidence Criteria \n### Subsections \nAdditional Avenues of Investigation, Recommendation \n### Page Range \n"},
    {"content": "### Document Title \n[Unit 2: None - Disclosure Misrepresentation](localhost:8080/) \n### Section Title \nEvidence Criteria \n### Subsections \nAdditional Avenues of Investigation, Recommendation \n### Page Range \n"}
  ]
}
```
