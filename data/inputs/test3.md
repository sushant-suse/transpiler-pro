# Heading Level 1

## Heading Level 2

### Heading Level 3

#### Heading Level 4

##### Heading Level 5
###### Heading Level 6

:::info
It will be developed by the community. It is an info block.
:::

:::note
It will be developed by the communiti. It is a note block.
:::

This is a paragraph with **bold text**, *italic text*, and `inline code`. 

> **Note**:
> This is a blockquote often used as a note in Markdown.

> **Note:**
> This is another blockquote often used as a note in Markdown.

---

### Lists and Sublists
* Item 1
* Item 2
    * Sub-item A
    * Sub-item B

### Numbered Lists

1. Numbered List
2. Another item

### Mixed lists

* Item A
* Item B
    * Sub-item of A
    * Sub-item of B
1. First Numbered item
2. Second Numbered item

### Links and Images

You can find more details at [SUSE Documentation](https://www.suse.com).

Check out [Google](https://www.google.com) for more info.

### Media

![Alt text for image](https://example.com/image.png)

### Code Blocks

```python
def check_status():
    status = "Active"
    print(f"System is {status}")
```

```yaml
version: "3"
services:
```

```bash
echo "This is a bash code block"
```

### Tables

| Service | Port | Protocol |
| :--- | :---: | ---: |
| HTTP | 80 | TCP |
| HTTPS | 443 | TCP |
| SSH | 22 | TCP |

### Details

<details>
<summary>Click here for secrets</summary>
The password will be prompted by the terminal.
</details>

### Edge Cases
* Item with `code` and **bold**
    1. Nested number 1
    2. Nested number 2
* Back to bullet

| Feature | Description |
| --- | --- |
| Multi-line | This is line 1 <br> This is line 2 |

:::tip
#### Heading inside Admonition
This should still be wrapped in tip delimiters.
:::

### Navigation and Cross-References

See the [CRD Schedule](./reference/crds/schedule_v1alpha1.md) for details.
Go back to [the main guide](../installation-guide.md).
Check the [JSON Schema](./reference/crds/schedule_v1alpha1.json).