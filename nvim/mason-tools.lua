-- shfmt comes from mise (pinned in mise.toml) rather than Mason's unpinned prebuilt binary.
return {
  {
    "mason-org/mason.nvim",
    opts = function(_, opts)
      opts.ensure_installed = vim.tbl_filter(function(tool)
        return tool ~= "shfmt"
      end, opts.ensure_installed or {})
    end,
  },
}
