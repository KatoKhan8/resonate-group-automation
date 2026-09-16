# HeyReach /list/AddLeadsToListV2 - established schema

**Date:** 2026-09-15
**List used:** 940797 (Resonate-created, no campaign, `campaignIds: []`)

## The working request body

```json
{
  "listId": 940797,
  "leads": [
    {
      "profileUrl": "https://www.linkedin.com/in/<profile_hash>",
      "firstName": "<first_name_hash>",
      "lastName": "<last_name_hash>"
    }
  ]
}
```

**Response:**
```json
{"addedLeadsCount": 1, "updatedLeadsCount": 0, "failedLeadsCount": 0}
```

**Readback via `/list/GetLeadsFromList`:**
```json
{
  "profile_url": "https://www.linkedin.com/in/<profile_hash>",
  "provider_profile_id": null,
  "first_name": "<first_name_hash>",
  "last_name": "<last_name_hash>"
}
```

## Required fields per lead object

| Field        | Type   | Required | Notes                                |
|-------------|--------|----------|--------------------------------------|
| profileUrl  | string | YES      | LinkedIn profile URL                 |
| firstName   | string | YES      | Silent drop if missing               |
| lastName    | string | YES      | Silent drop if missing               |
| companyName | string | no       | Optional                             |
| position    | string | no       | Optional                             |
| location    | string | no       | Optional                             |
| summary     | string | no       | Optional                             |
| about       | string | no       | Optional                             |
| emailAddress| string | no       | Optional                             |
| customUserFields | array | no   | `[{name, value}]` pairs             |

## The trap

The provider **silently ignores** lead objects it does not recognise. An empty
lead object `{}` returns the same `0/0/0` as a fully populated one. A lead
missing `firstName` or `lastName` returns `0/0/0` with no error. The only way
to verify a lead was added is to read the list back via `/list/GetLeadsFromList`.

## Field name difference from the campaign route

| Context   | Field for LinkedIn URL | Wrapper               |
|-----------|----------------------|-----------------------|
| Campaign  | `profileUrl`         | `lead` inside `accountLeadPairs` |
| List      | `profileUrl`         | Direct in `leads[]` array         |

The existing `add_leads_to_list` function used `linkedInUrl` - a field name
that does not exist on this route. The campaign route also uses `profileUrl`
but inside a different wrapper (`accountLeadPairs[].lead.profileUrl`). The
list route takes the lead object directly in the `leads` array.

## Shapes that silently failed (0/0/0)

All tested against list 940797 with real profiles HeyReach resolves via
`/lead/GetLead` (`<name_hash_1>` `linkedin_id=<id_hash_1>`, `<name_hash_2>`
`linkedin_id=<id_hash_2>`):

1. `{linkedInUrl, firstName, lastName, companyName, position}` - wrong field name
2. `{profileUrl}` alone - missing required firstName/lastName
3. `{lead: {profileUrl}}` - wrong wrapper
4. `{linkedInAccountId, leads: [{profileUrl}]}` - campaign shape, wrong here
5. `{}` empty lead - silently ignored
6. `{linkedin_id: "389277834"}` - not a recognised field
7. `{linkedInUserProfileId: "389277834"}` - not a recognised field
8. `{linkedinId: "389277834"}` - not a recognised field (camelCase)
9. `{linkedInUrl: "389277834"}` (integer) - wrong field, wrong type
10. `{linkedInUserProfile: {profileUrl}}` - wrong nesting
11. `{linkedInUserProfile: {linkedin_id}}` - wrong nesting
12. `{linkedInAccountId, lead: {profileUrl}}` - campaign shape in list clothing

## Documentation sources

- n8n HeyReach community node source: `ListOperations.ts` and `ListParameters.ts`
  at https://github.com/bcharleson/n8n-nodes-heyreach
- HeyReach CLI: https://github.com/bcharleson/heyreach-cli
  (`src/commands/lists/add-leads.ts`)
- Postman collection: https://documenter.getpostman.com/view/23808049/2sA2xb5F75
  (JavaScript-rendered, not machine-readable)
- The official docs.heyreach.io domain does not resolve (2026-09-15)

## Proof

The lead was added and read back:

    POST /list/AddLeadsToListV2
    {"listId": 940797, "leads": [{"profileUrl": "https://www.linkedin.com/in/<profile_hash>", "firstName": "<first_name_hash>", "lastName": "<last_name_hash>"}]}
    -> {"addedLeadsCount": 1, "updatedLeadsCount": 0, "failedLeadsCount": 0}

    POST /list/GetLeadsFromList
    {"listId": 940797, "offset": 0, "limit": 100}
    -> totalCount: 1, items: [{profileUrl: "https://www.linkedin.com/in/<profile_hash>", firstName: "<first_name_hash>", lastName: "<last_name_hash>"}]
