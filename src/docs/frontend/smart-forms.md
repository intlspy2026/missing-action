# Smart Investigator - Smart Forms

* By Mitchell Jeffery
* 5 min

---

Smart Forms enables Agents to collect data from users in a user-friendly manner. It functions as a rendering engine that dynamically generates form inputs based on a JSON schema provided by the agent. Once the user submits the form, the Smart Form serializes the input data and returns it to the Master Agent as a JSON.

## Smart Form Container

Smart Forms can be used within a Workflow Stage artifact. Only **one** smart form is supported per Workflow Stage.

You can specify whether or not a confirmation dialog should appear before submission with the `confirm_submit` property.

You should only pass Smart Inputs and Smart Groups to the `data` property of a Smart Form container.

### Smart Form Container Schema

```json
{
  "type": "smart_form",
  "confirm_submit": true,
  "data": []
}
```

---

## Smart Inputs

Smart Inputs are components based on the current Figma designs. If new smart inputs are required, they will need to be deployed from the frontend before Agents can start rendering them dynamically.

### Field Types

| Type | Description |
| :--- | :--- |
| `text` | A single-line text field |
| `textarea` | A multi-line text field |
| `number` | A control for entering a number. Displays a spinner and adds default validation |
| `select` | A single-item dropdown |
| `combobox` | A single-item dropdown with search |
| `multiselect_combobox` | A multi-item dropdown with search |
| `chipbox` | A multi-item view for toggleable values |
| `keyvalue_mapper` | A key-value input that allows users to provide values to predefined keys |
| `info` | An element that takes no input but displays a description. <br><br>• Forces N/A to be displayed <br><br>• Cannot be marked as required |
| `info_chipbox` | An element that takes input in the form of a chipbox but also includes a description. <br><br>• Forces N/A to be displayed |

### Field Schema

All keys in the Smart Field schema are shared unless explicitly stated otherwise.

| Key | Description | Value Type | Example |
| :--- | :--- | :--- | :--- |
| `type` | The Smart Field type | `"text"` \| `"textarea"` \| `"number"` \| `"select"` \| `"combobox"` \| `"multiselect_combobox"` \| `"chipbox"` \| `"keyvalue_mapper"` \| `"info"` \| `"info_chipbox"` | `type: "textarea"` |
| `id` | A unique identifier for the Smart Field, included in the returned serialized data | string | `id: "1"` |
| `label` | Human readable label for the Smart Field, displayed to the user on the frontend | string | `label: "Extra Information"` |
| `placeholder` | Text displayed when Smart Field is empty | string | `placeholder: "Enter any additional information"` |
| `default_value` | Text that will pre-populate the input field. Variable type depends on Smart Field Type: <br>• text: string <br>• textarea: string <br>• number: number <br>• select: string <br>• combobox: string <br>• multiselect_combobox: list[string] <br>• chipbox: list[string] <br>• keyvalue_mapper: list[string] | string \| list[string] \| number | `default_value: "default"`, `default_value: ["default"]`, `default_value: 0` |
| `hint` | Additional information about the Smart Field (optional) | string | `hint: "This should include anything about x, y or z"` |
| `required` | Marks the Smart Field as required | boolean | `required: true` |
| `pattern` | An optional regex validator for Smart Inputs. [Regex reference](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide/Regular_expressions), flags can be omitted. | dict | `pattern: { value: "^[A-Za-z]+$", flags: "i", message: "Only letters are allowed" }` |
| `data` | Defines the input data for the respective type. Only used for: `select`, `combobox`, `multiselect_combobox`, `chipbox`, `keyvalue_mapper` | array[object] | `data: [{ value: "value_1", label: "label_1" }]` |
| `not_applicable` | Defines if the N/A Checkbox is to be displayed for the input | boolean | `not_applicable: true` |

---

## Smart Groups

Smart Groups are components that allow you to group smart inputs together. Smart Groups are recursive and can be nested as required.

### Group Types

| Type | Description |
| :--- | :--- |
| `accordion` | A group of components that can be hidden from the user |
| `lookup` | A group of components that renders conditionally for a given field value |
| `title` | A group of components that renders with an additional title. |

### Group Schema

| Key | Description | Value Type | Example |
| :--- | :--- | :--- | :--- |
| `type` | The Smart Group type | `"accordion"` \| `"lookup"` \| `"title"` | `type: "accordion"` |
| `id` | A unique identifier for the Smart Group | string | `id: "1"` |
| `data` | An array of groups | array[object] | `data: [{ value: "value_1", components: [] }]` |
| `metadata` | Metadata for the respective type. Only used for: `lookup` | object | |

### Value Schema

| Key | Description | Value Type | Example |
| :--- | :--- | :--- | :--- |
| `value` | Name of the section | string | `value: "Section 1"` |
| `open` | Toggle to set the accordion group as open on first load (default false). Only for: `accordion` | bool | `open: true` |
| `components` | Components to include | array[object] | `components: [...]` |

### Example

```json
[
  {
    "type": "accordion",
    "id": "group_1",
    "data": [
      {
        "value": "Section 1",
        "open": true,
        "components": [
          {
            "type": "text",
            "id": "example",
            "label": "Test Input Label",
            "placeholder": "Enter text",
            "hint": "This is an example input field hint",
            "required": true,
            "pattern": { "value": "^[A-Za-z]+$", "message": "Only letters are allowed" }
          }
        ]
      },
      {
        "value": "Section 2",
        "open": false,
        "components": [
          {
            "type": "text",
            "id": "example",
            "label": "Test Input Label",
            "placeholder": "Enter text",
            "hint": "This is an example input field hint",
            "required": true,
            "pattern": { "value": "^[A-Za-z]+$", "message": "Only letters are allowed" }
          }
        ]
      }
    ]
  },
  {
    "type": "select",
    "id": "field_group_key",
    "label": "Select a Brand",
    "data": [
      { "value": "aami", "label": "AAMI" },
      { "value": "shannons", "label": "Shannons" },
      { "value": "suncorp", "label": "Suncorp" }
    ]
  },
  {
    "type": "lookup",
    "id": "group_2",
    "data": [
      {
        "value": "aami",
        "components": [
          {
            "type": "text",
            "id": "example",
            "label": "Test Input Label",
            "placeholder": "Enter text",
            "hint": "This is an example input field hint",
            "required": true,
            "pattern": { "value": "^[A-Za-z]+$", "message": "Only letters are allowed" }
          }
        ]
      },
      {
        "value": "shannons",
        "components": [
          {
            "type": "text",
            "id": "example",
            "label": "Test Input Label",
            "placeholder": "Enter text",
            "hint": "This is an example input field hint",
            "required": true,
            "pattern": { "value": "^[A-Za-z]+$", "message": "Only letters are allowed" }
          }
        ]
      },
      {
        "value": "suncorp",
        "components": [
          {
            "type": "text",
            "id": "example",
            "label": "Test Input Label",
            "placeholder": "Enter text",
            "hint": "This is an example input field hint",
            "required": true,
            "pattern": { "value": "^[A-Za-z]+$", "message": "Only letters are allowed" }
          }
        ]
      }
    ],
    "metadata": {
      "fieldId": "field_group_key"
    }
  },
  {
    "type": "title",
    "id": "mock_title_group",
    "data": [
      {
        "open": false,
        "value": "Information",
        "components": [
          {
            "id": "input_1",
            "type": "info",
            "label": "Example Question 2",
            "description": "Review this information and mark N/A if it does not apply.",
            "defaultValue": false
          },
          {
            "id": "input_2",
            "data": [
              {
                "label": "Option A",
                "value": "input_2_option_a",
                "description": "First option."
              },
              {
                "label": "Option B",
                "value": "input_2_option_b",
                "description": "Second option."
              },
              {
                "label": "Option C",
                "value": "input_2_option_c",
                "description": "Third option."
              }
            ],
            "type": "info_chipbox",
            "label": "Example Question 3",
            "required": true,
            "description": "Review this information and mark N/A if it does not apply.",
            "defaultValue": [],
            "notApplicable": true
          }
        ]
      }
    ]
  }
]
```
