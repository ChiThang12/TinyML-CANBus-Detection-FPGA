module feature_selector (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        valid_in,
    input  wire [2:0]  feature_id,
    input  wire [31:0] feature_0_scaled,
    input  wire [31:0] feature_1_scaled,
    input  wire [31:0] feature_2_scaled,
    input  wire [31:0] feature_3_scaled,
    input  wire [31:0] feature_4_scaled,
    input  wire [31:0] feature_5_scaled,
    output reg  [31:0] selected_feature,
    output reg         valid_out,
    output reg         error             // Invalid feature_id
);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            selected_feature <= 32'b0;
            valid_out <= 1'b0;
            error <= 1'b0;
        end else if (valid_in) begin
            error <= 1'b0;
            valid_out <= 1'b1;
            case (feature_id)
                3'd0: selected_feature <= feature_0_scaled;
                3'd1: selected_feature <= feature_1_scaled;
                3'd2: selected_feature <= feature_2_scaled;
                3'd3: selected_feature <= feature_3_scaled;
                3'd4: selected_feature <= feature_4_scaled;
                3'd5: selected_feature <= feature_5_scaled;
                default: begin
                    selected_feature <= 32'b0;
                    error <= 1'b1;  // Invalid feature ID
                end
            endcase
        end else begin
            valid_out <= 1'b0;
        end
    end

endmodule
