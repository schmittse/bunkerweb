import { contentIndex } from "@utils/tabindex.js";

/**
 *  @name utils/tabulator.js
 *  @description This file contains utils to work with the tabulator library and Vue instance.
 */

/**
 *  @name addColumnsWidth
 *  @description Add min and max width to the column object in case we have the right format.
 *  Case already a custom max or min width, will be ignored.
 *  @param {Object} column -  The column object to update in case we have the right format.
 *  @param {String|Number} [colMinWidth=0] - The minimum width for the column. Case 0 or invalid, will be ignored.
 *  @param {String|Number} [colMaxWidth=0] - The minimum width for the column. Case 0 or invalid, will be ignored.
 *  @returns {Void}
 */
function addColumnsWidth(column, colMinWidth = 0, colMaxWidth = 0) {
  try {
    if (+colMinWidth > 0 && !("minWidth" in column))
      column.minWidth = colMinWidth;
    if (+colMaxWidth > 0 && !("maxWidth" in column))
      column.maxWidth = colMaxWidth;

    // Check that minWidth is less than maxWidth
    if (
      "minWidth" in column &&
      "maxWidth" in column &&
      column.minWidth > column.maxWidth
    ) {
      column.minWidth = column.maxWidth;
    }
  } catch (e) {
    console.error(e);
  }
}

/**
 *  @name addColumnsSorter
 *  @description This is a wrapper that will execute every sorter function in order to add a new sorter to the tabulator library.
 *  @example { title: "Icon", field: "icon", formatter: "icons" }
 *  @param {Object} column -  The column object to update in case we have the right format.
 *  @returns {Void}
 */
function addColumnsSorter(column) {
  if (!("formatter" in column)) return;
  const formatName = column.formatter.toLowerCase();
  _sortButtonGroup(column, formatName);
  _sortFields(column, formatName);
  _sortIcons(column, formatName);
  _sortText(column, formatName);
}

/**
 *  @name _baseSorter
 *  @description Base sorter we will use for each custom component.
 *  @param {String} aValue - The value of the first row to compare.
 *  @param {String} bValue -  The value of the second row to compare.
 *  @returns {String|Number} - The result of the comparison
 */
function _baseSorter(aValue, bValue, params) {
  let alignEmptyValues = params.alignEmptyValues;
  let emptyAlign = 0;
  let locale;

  if (aValue && bValue) {
    locale =
      typeof params.locale == "boolean" ? this.langLocale() : params.locale;

    return String(aValue)
      .toLowerCase()
      .localeCompare(String(bValue).toLowerCase(), locale);
  }

  if (!aValue) emptyAlign = !bValue ? 0 : -1;
  if (!bValue) emptyAlign = 1;

  //fix empty values in position
  if (
    (alignEmptyValues === "top" && dir === "desc") ||
    (alignEmptyValues === "bottom" && dir === "asc")
  ) {
    emptyAlign *= -1;
  }

  return emptyAlign;
}

/**
 *  @name _sortButtonGroup
 *  @description Add sorter for ButtonGorup components in the tabulator. This will merge text from all buttons and sort them.
 *  @example { title: "actions", field: "actions", formatter: "buttongroup" }
 *  @param {Object} column -  The column object to update in case we have the right format.
 *  @param {String} formatName - Check if the current column format is the right one.
 *  @returns {Void}
 */
function _sortButtonGroup(column, formatName) {
  if (formatName !== "buttongroup") return;
  column.sorter = (a, b, aRow, bRow, column, dir, params) => {
    const aButtons = a?.buttons;
    const bButtons = b?.buttons;

    const aValue = aButtons.map((btn) => btn.data.text).join(" ") || "";
    const bValue = bButtons.map((btn) => btn.data.text).join(" ") || "";
    console.log(aValue, bValue);
    return _baseSorter(aValue, bValue, params);
  };
}

/**
 *  @name _sortFields
 *  @description Add sorter for Fields components in the tabulator. This will sort the fields by the value of the setting object.
 *  @example { title: "Input", field: "input", formatter: "fields" }
 *  @param {Object} column -  The column object to update in case we have the right format.
 *  @param {String} formatName - Check if the current column format is the right one.
 *  @returns {Void}
 */
function _sortFields(column, formatName) {
  if (formatName !== "fields") return;
  column.sorter = (a, b, aRow, bRow, column, dir, params) => {
    const aSetting = a.setting;
    const bSetting = b.setting;

    const aValue = aSetting?.value || "";
    const bValue = bSetting?.value || "";
    return _baseSorter(aValue, bValue, params);
  };
}

/**
 *  @name _sortIcons
 *  @description Add sorter for Icons components in the tabulator.
 *  @example { title: "Icon", field: "icon", formatter: "icons" }
 *  @param {Object} column -  The column object to update in case we have the right format.
 *  @param {String} formatName - Check if the current column format is the right one.
 *  @returns {Void}
 */
function _sortIcons(column, formatName) {
  if (formatName !== "icons") return;
  column.sorter = (a, b, aRow, bRow, column, dir, params) => {
    const aValue = a.iconName;
    const bValue = b.iconName;
    return _baseSorter(aValue, bValue, params);
  };
}

/**
 *  @name _sortText
 *  @description Add sorter for Text components in the tabulator. Under the hood, this will use the default tabulator sorter for strings.
 *  @example { title: "Icon", field: "icon", formatter: "icons" }
 *  @param {Object} column -  The column object to update in case we have the right format.
 *  @param {String} column - Check if the current column format is the right one.
 *  @returns {Void}
 */
function _sortText(column, formatName) {
  if (formatName !== "text") return;
  column.sorter = (a, b, aRow, bRow, column, dir, params) => {
    const aValue = a.text;
    const bValue = b.text;
    return _baseSorter(aValue, bValue, params);
  };
}

/**
 *  @name a11yTable
 *  @description Wrapper to add some accessibility to the table.
 *  @returns {Void}
 */
function a11yTable() {
  _a11ySortable();
  _a11yFooter();
}

/**
 *  @name _a11ySortable
 *  @description Allow the user to get to the sortable header by pressing the tab key.
 *  The user can then press the enter key to sort the column.
 *  @returns {Void}
 */
function _a11ySortable() {
  const sortableHeaders = document.querySelectorAll(
    ".tabulator-col.tabulator-sortable .tabulator-col-sorter"
  );
  for (let i = 0; i < sortableHeaders.length; i++) {
    // Try to get child or keep current
    const sortableHeader = sortableHeaders[i].closest(".tabulator-col-content");
    if (!sortableHeader.hasAttribute("role"))
      sortableHeader.setAttribute("role", "button");
    sortableHeader.setAttribute("tabindex", contentIndex);
    sortableHeader.setAttribute("data-sort", "true");
  }
  // Add eventlistener to make sort working with enter key
  document.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && e.target.getAttribute("data-sort") === "true") {
      e.target.click();
    }
  });
}

/**
 *  @name _a11yFooter
 *  @description Update pagination tabindex to get continuity in the tab order in the table footer.
 *  @returns {Void}
 */
function _a11yFooter() {
  try {
    const tableFooter = document.querySelector(".tabulator-footer");
    // query button and select tag
    const interactiveElements = tableFooter.querySelectorAll("button, select");
    for (let i = 0; i < interactiveElements.length; i++) {
      interactiveElements[i].setAttribute("tabindex", contentIndex);
    }
  } catch (e) {}
}

/**
 *  @name applyTableFilter
 *  @description Apply setting filter to the tabulator instance.
 *  We can't easily add filter after another, so we need to remove the previous one and add all new ones at once.
 *  @example { "filter-1" : { type: "keywords", fields: ["text", "icon"], setting: {}, value : "test" }}
 *  @param {Object} tableInstance - The table instance to apply the filter.
 *  @param {Object} filters -  All filters to apply to the table.
 *  @param {String|Number|Regex} value - The value to apply to the filter.
 *  @returns {Void}
 */
function applyTableFilter(tableInstance, filters) {
  // loop on dict filters
  const filtersSend = [];
  for (const [key, filter] of Object.entries(filters)) {
    const filters = [];
    const inpType = filter.setting.inpType;
    const filterType = filter.type;
    const value = filter.value;
    const fields = filter.fields;

    // Cases we don't want to apply filter
    if (value === "") continue;
    if (value === "all" && inpType === "select") continue;

    // format value if needed
    if (filterType === "number") value = +value;
    if (filterType === "regex") value = new RegExp(value, "i");
    for (let i = 0; i < fields.length; i++) {
      filters.push({ field: fields[i], type: filterType, value: value });
    }
    filtersSend.push(filters);
  }

  tableInstance.setFilter(filtersSend);
}

/**
 *  @name overrideDefaultFilters
 *  @description Create isomorphic filters for the tabulator library.
 *  Override default filters retrieving the right value for each custom components.
 *  @returns {object} - The custom filter function.
 */
function overrideDefaultFilters() {
  //
  const getRightKey = (rowValue) => {
    const value =
      rowValue?.buttons?.map((btn) => btn.data.text).join(" ") ||
      rowValue?.setting?.value ||
      rowValue?.value?.toLowerCase() ||
      rowValue?.text?.toLowerCase() ||
      "";

    return value;
  };

  return {
    //equal to
    "=": function (filterVal, rowVal, rowData, filterParams) {
      const value = getRightKey(rowVal);
      return value == filterVal ? true : false;
    },

    //less than
    "<": function (filterVal, rowVal, rowData, filterParams) {
      const value = getRightKey(rowVal);
      return value < filterVal ? true : false;
    },

    //less than or equal to
    "<=": function (filterVal, rowVal, rowData, filterParams) {
      const value = getRightKey(rowVal);
      return value <= filterVal ? true : false;
    },

    //greater than
    ">": function (filterVal, rowVal, rowData, filterParams) {
      const value = getRightKey(rowVal);
      return value > filterVal ? true : false;
    },

    //greater than or equal to
    ">=": function (filterVal, rowVal, rowData, filterParams) {
      const value = getRightKey(rowVal);
      return value >= filterVal ? true : false;
    },

    //not equal to
    "!=": function (filterVal, rowVal, rowData, filterParams) {
      const value = getRightKey(rowVal);
      return value != filterVal ? true : false;
    },

    regex: function (filterVal, rowVal, rowData, filterParams) {
      const value = getRightKey(rowVal);

      if (typeof filterVal == "string") filterVal = new RegExp(filterVal);

      return filterVal.test(value);
    },

    //contains the string
    like: function (filterVal, rowVal, rowData, filterParams) {
      const value = getRightKey(rowVal);

      if (filterVal === null || typeof filterVal === "undefined")
        return value === filterVal ? true : false;

      if (typeof value !== "undefined" && value !== null)
        return (
          String(value).toLowerCase().indexOf(filterVal.toLowerCase()) > -1
        );

      return false;
    },

    //contains the keywords
    keywords: function (filterVal, rowVal, rowData, filterParams) {
      let value = getRightKey(rowVal);
      const keywords = filterVal
        .toLowerCase()
        .split(
          typeof filterParams.separator === "undefined"
            ? " "
            : filterParams.separator
        );

      value = String(
        value === null || typeof value === "undefined" ? "" : value
      ).toLowerCase();

      const matches = [];

      keywords.forEach((keyword) => {
        if (value.includes(keyword)) {
          matches.push(true);
        }
      });

      return filterParams.matchAll
        ? matches.length === keywords.length
        : !!matches.length;
    },

    //starts with the string
    starts: function (filterVal, rowVal, rowData, filterParams) {
      const value = getRightKey(rowVal);

      if (filterVal === null || typeof filterVal === "undefined")
        return value === filterVal ? true : false;

      if (typeof value !== "undefined" && value !== null)
        return String(value).toLowerCase().startsWith(filterVal.toLowerCase());

      return false;
    },

    //ends with the string
    ends: function (filterVal, rowVal, rowData, filterParams) {
      const value = getRightKey(rowVal);

      if (filterVal === null || typeof filterVal === "undefined")
        return value === filterVal ? true : false;

      if (typeof value !== "undefined" && value !== null)
        return String(value).toLowerCase().endsWith(filterVal.toLowerCase());

      return false;
    },

    //in array
    in: function (filterVal, rowVal, rowData, filterParams) {
      const value = getRightKey(rowVal);

      if (Array.isArray(filterVal))
        return filterVal.length ? filterVal.indexOf(value) > -1 : true;

      console.warn("Filter Error - filter value is not an array:", filterVal);
      return false;
    },
  };
}

export {
  addColumnsSorter,
  addColumnsWidth,
  a11yTable,
  applyTableFilter,
  overrideDefaultFilters,
};
