export namespace contracts {
	
	export class ApplyChangesModel {
	    file_path: string;
	    new_content: string;
	    repo_path: string;
	    line_number: number;
	    new_start_line_number: number;
	    number_of_lines_removed_from_old: number;
	    number_of_lines_added_in_new: number;
	    old_start_line_number: number;
	    old_content: string;
	    allow_fallback_search: boolean;
	
	    static createFrom(source: any = {}) {
	        return new ApplyChangesModel(source);
	    }
	
	    constructor(source: any = {}) {
	        if ('string' === typeof source) source = JSON.parse(source);
	        this.file_path = source["file_path"];
	        this.new_content = source["new_content"];
	        this.repo_path = source["repo_path"];
	        this.line_number = source["line_number"];
	        this.new_start_line_number = source["new_start_line_number"];
	        this.number_of_lines_removed_from_old = source["number_of_lines_removed_from_old"];
	        this.number_of_lines_added_in_new = source["number_of_lines_added_in_new"];
	        this.old_start_line_number = source["old_start_line_number"];
	        this.old_content = source["old_content"];
	        this.allow_fallback_search = source["allow_fallback_search"];
	    }
	}
	export class CherryPickRequestModel {
	    repo_path: string;
	    organization: string;
	    project: string;
	    repository_name: string;
	    azure_pat: string;
	    defaults_path?: string;
	    source_branch: string;
	    target_branch: string;
	    commit_hashes?: string[];
	
	    static createFrom(source: any = {}) {
	        return new CherryPickRequestModel(source);
	    }
	
	    constructor(source: any = {}) {
	        if ('string' === typeof source) source = JSON.parse(source);
	        this.repo_path = source["repo_path"];
	        this.organization = source["organization"];
	        this.project = source["project"];
	        this.repository_name = source["repository_name"];
	        this.azure_pat = source["azure_pat"];
	        this.defaults_path = source["defaults_path"];
	        this.source_branch = source["source_branch"];
	        this.target_branch = source["target_branch"];
	        this.commit_hashes = source["commit_hashes"];
	    }
	}
	export class CommitAndPushRequestModel {
	    repo_path: string;
	    organization: string;
	    project: string;
	    repository_name: string;
	    azure_pat: string;
	    defaults_path?: string;
	    branch_name: string;
	    base_branch: string;
	    selected_serials?: number[];
	    commit_message: string;
	
	    static createFrom(source: any = {}) {
	        return new CommitAndPushRequestModel(source);
	    }
	
	    constructor(source: any = {}) {
	        if ('string' === typeof source) source = JSON.parse(source);
	        this.repo_path = source["repo_path"];
	        this.organization = source["organization"];
	        this.project = source["project"];
	        this.repository_name = source["repository_name"];
	        this.azure_pat = source["azure_pat"];
	        this.defaults_path = source["defaults_path"];
	        this.branch_name = source["branch_name"];
	        this.base_branch = source["base_branch"];
	        this.selected_serials = source["selected_serials"];
	        this.commit_message = source["commit_message"];
	    }
	}
	export class ConfigModel {
	    repo_path: string;
	    ai_model?: string;
	    max_tokens?: number;
	    organization?: string;
	    project?: string;
	    repository_name?: string;
	    pull_request_id?: string;
	    azure_pat?: string;
	    is_local?: boolean;
	    review?: string;
	
	    static createFrom(source: any = {}) {
	        return new ConfigModel(source);
	    }
	
	    constructor(source: any = {}) {
	        if ('string' === typeof source) source = JSON.parse(source);
	        this.repo_path = source["repo_path"];
	        this.ai_model = source["ai_model"];
	        this.max_tokens = source["max_tokens"];
	        this.organization = source["organization"];
	        this.project = source["project"];
	        this.repository_name = source["repository_name"];
	        this.pull_request_id = source["pull_request_id"];
	        this.azure_pat = source["azure_pat"];
	        this.is_local = source["is_local"];
	        this.review = source["review"];
	    }
	}
	export class PRFeatureContextRequestModel {
	    repo_path: string;
	    organization: string;
	    project: string;
	    repository_name: string;
	    azure_pat: string;
	    defaults_path?: string;
	    feature_id: number;
	
	    static createFrom(source: any = {}) {
	        return new PRFeatureContextRequestModel(source);
	    }
	
	    constructor(source: any = {}) {
	        if ('string' === typeof source) source = JSON.parse(source);
	        this.repo_path = source["repo_path"];
	        this.organization = source["organization"];
	        this.project = source["project"];
	        this.repository_name = source["repository_name"];
	        this.azure_pat = source["azure_pat"];
	        this.defaults_path = source["defaults_path"];
	        this.feature_id = source["feature_id"];
	    }
	}
	export class PRReviewersRequestModel {
	    repo_path: string;
	    organization: string;
	    project: string;
	    repository_name: string;
	    azure_pat: string;
	    defaults_path?: string;
	    limit?: number;
	    preferred_emails?: string[];
	
	    static createFrom(source: any = {}) {
	        return new PRReviewersRequestModel(source);
	    }
	
	    constructor(source: any = {}) {
	        if ('string' === typeof source) source = JSON.parse(source);
	        this.repo_path = source["repo_path"];
	        this.organization = source["organization"];
	        this.project = source["project"];
	        this.repository_name = source["repository_name"];
	        this.azure_pat = source["azure_pat"];
	        this.defaults_path = source["defaults_path"];
	        this.limit = source["limit"];
	        this.preferred_emails = source["preferred_emails"];
	    }
	}
	export class PRWorkItemFamilyRequestModel {
	    repo_path: string;
	    organization: string;
	    project: string;
	    repository_name: string;
	    azure_pat: string;
	    defaults_path?: string;
	    work_item_id: number;
	
	    static createFrom(source: any = {}) {
	        return new PRWorkItemFamilyRequestModel(source);
	    }
	
	    constructor(source: any = {}) {
	        if ('string' === typeof source) source = JSON.parse(source);
	        this.repo_path = source["repo_path"];
	        this.organization = source["organization"];
	        this.project = source["project"];
	        this.repository_name = source["repository_name"];
	        this.azure_pat = source["azure_pat"];
	        this.defaults_path = source["defaults_path"];
	        this.work_item_id = source["work_item_id"];
	    }
	}
	export class PRWorkflowBaseRequestModel {
	    repo_path: string;
	    organization: string;
	    project: string;
	    repository_name: string;
	    azure_pat: string;
	    defaults_path?: string;
	
	    static createFrom(source: any = {}) {
	        return new PRWorkflowBaseRequestModel(source);
	    }
	
	    constructor(source: any = {}) {
	        if ('string' === typeof source) source = JSON.parse(source);
	        this.repo_path = source["repo_path"];
	        this.organization = source["organization"];
	        this.project = source["project"];
	        this.repository_name = source["repository_name"];
	        this.azure_pat = source["azure_pat"];
	        this.defaults_path = source["defaults_path"];
	    }
	}
	export class RaiseNewPRRequestModel {
	    repo_path: string;
	    organization: string;
	    project: string;
	    repository_name: string;
	    azure_pat: string;
	    defaults_path?: string;
	    feature_id: number;
	    selected_serials?: number[];
	    reviewer_ids?: string[];
	    reviewer_ids_by_branch?: Record<string, Array<string>>;
	    target_branches?: string[];
	    additional_work_item_ids?: number[];
	    commit_message?: string;
	
	    static createFrom(source: any = {}) {
	        return new RaiseNewPRRequestModel(source);
	    }
	
	    constructor(source: any = {}) {
	        if ('string' === typeof source) source = JSON.parse(source);
	        this.repo_path = source["repo_path"];
	        this.organization = source["organization"];
	        this.project = source["project"];
	        this.repository_name = source["repository_name"];
	        this.azure_pat = source["azure_pat"];
	        this.defaults_path = source["defaults_path"];
	        this.feature_id = source["feature_id"];
	        this.selected_serials = source["selected_serials"];
	        this.reviewer_ids = source["reviewer_ids"];
	        this.reviewer_ids_by_branch = source["reviewer_ids_by_branch"];
	        this.target_branches = source["target_branches"];
	        this.additional_work_item_ids = source["additional_work_item_ids"];
	        this.commit_message = source["commit_message"];
	    }
	}
	export class StaticChecksRequestModel {
	    repo_path: string;
	    scope?: string;
	    organization?: string;
	    project?: string;
	    repository_name?: string;
	    pull_request_id?: string;
	    azure_pat?: string;
	    is_local?: boolean;
	    file_paths?: string[];
	
	    static createFrom(source: any = {}) {
	        return new StaticChecksRequestModel(source);
	    }
	
	    constructor(source: any = {}) {
	        if ('string' === typeof source) source = JSON.parse(source);
	        this.repo_path = source["repo_path"];
	        this.scope = source["scope"];
	        this.organization = source["organization"];
	        this.project = source["project"];
	        this.repository_name = source["repository_name"];
	        this.pull_request_id = source["pull_request_id"];
	        this.azure_pat = source["azure_pat"];
	        this.is_local = source["is_local"];
	        this.file_paths = source["file_paths"];
	    }
	}

}

